"""Task-based model routing and pre-flight cost estimates (MODEL_PROFILES.yaml `tasks`).

Routing — each AI operation has its own model, reasoning effort and output cap, so deep multi-hop work (architecture,
flows, drift, integration design) gets Terra with high effort while rewriting and page search run on Luna with low
effort. Blocked models (Sol) are never routed to, whatever is requested or stored as a preference.

Estimates — before a call the UI can show what it will cost:
* input tokens: counted from the actual text when it is known (`count_tokens`), else the task's typical prompt
  (system prompt + evidence budget) or, better, the average of the last calls of that task in this organization;
* output tokens (visible + reasoning, which are billed as output): the ledger's history for (task, model) when there are
  at least MIN_HISTORY calls, else the task's `expected_output_tokens` — and always an upper bound at the output cap;
* USD: the price table, or — for a model without a list price — the average LiteLLM-reported cost per token from history.
"""
from __future__ import annotations

import math
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select, text

from archtwin.common.db import unscoped
from archtwin.common.schema import llm_calls
from archtwin.intelligence import gateway, usage

MIN_HISTORY = 3
HISTORY_DAYS = 30
EFFORTS = ("minimal", "low", "medium", "high")
SYSTEM_PROMPT_TOKENS = 700           # typical system prompt + question framing


@dataclass(frozen=True)
class Task:
    operation: str
    model: str
    reasoning_effort: str
    max_output_tokens: int
    expected_output_tokens: int
    evidence_tokens: int
    purpose: str
    user_selectable: bool


@dataclass(frozen=True)
class Route:
    operation: str
    model: str
    reasoning_effort: str
    max_output_tokens: int
    overridden: bool                 # the user's model choice replaced the task's model


def blocked() -> set[str]:
    return set(gateway.profiles().get("blocked_models") or [])


def tasks() -> dict[str, Task]:
    out = {}
    for op, t in (gateway.profiles().get("tasks") or {}).items():
        effort = t.get("reasoning_effort", "medium")
        out[op] = Task(op, t["model"], effort if effort in EFFORTS else "medium", int(t.get("max_output_tokens", 4000)),
                       int(t.get("expected_output_tokens", 800)), int(t.get("evidence_tokens", 0)), t.get("purpose", op),
                       bool(t.get("user_selectable", False)))
    return out


def task(operation: str) -> Task:
    t = tasks().get(operation)
    return t or Task(operation, gateway.default_model(), "medium", 4000, 800, 2000, operation, False)


def _usable(model: str) -> bool:
    return model not in blocked() and gateway.is_available(model)


def route(operation: str, requested: str | None = None, preference: str | None = None) -> Route:
    """The model/effort/cap for one call. User choices only apply to user-selectable tasks and are validated server-side
    (an explicit request for a model that is not allowed is a 422; a stale preference is ignored)."""
    t = task(operation)
    if requested and requested in blocked():
        gateway.resolve_model(requested, None, [o["alias"] for o in gateway.selectable() if o["alias"] not in blocked()])   # raises 422
    if t.user_selectable and (requested or (preference and preference not in blocked())):
        m = gateway.resolve_model(requested, preference if preference not in blocked() else None,
                                  [o["alias"] for o in gateway.selectable() if o["alias"] not in blocked()])
        return Route(operation, m, t.reasoning_effort, t.max_output_tokens, m != t.model)
    if _usable(t.model):
        return Route(operation, t.model, t.reasoning_effort, t.max_output_tokens, False)
    fallback = gateway.resolve_model(None, None, [o["alias"] for o in gateway.selectable() if o["alias"] not in blocked()])
    return Route(operation, fallback, t.reasoning_effort, t.max_output_tokens, True)


_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def count_tokens(s: str) -> int:
    """BPE-free token estimate within ~10% for English prose, code and JSON: words and punctuation, long words split."""
    if not s:
        return 0
    n = 0
    for m in _TOKEN.finditer(s):
        w = m.group(0)
        if w.isalpha():                              # common words are one token up to ~10 letters
            n += 1 if len(w) <= 10 else math.ceil(len(w) / 5)
        else:                                        # identifiers with digits/underscores split more
            n += max(1, math.ceil(len(w) / 3.5))
    return max(n, math.ceil(len(s) / 4.5))


def messages_tokens(messages: list[dict[str, str]]) -> int:
    return sum(count_tokens(m.get("content", "")) + 4 for m in messages) + 3


async def history(org_id: uuid.UUID, operation: str, model: str) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(days=HISTORY_DAYS)
    async with unscoped() as conn:
        await conn.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": str(org_id)})
        cond = and_(llm_calls.c.org_id == org_id, llm_calls.c.operation == operation, llm_calls.c.model == model,
                    llm_calls.c.status == "ok", llm_calls.c.created_at >= since)
        r = (await conn.execute(select(
            func.count().label("n"), func.avg(llm_calls.c.input_tokens).label("avg_in"), func.avg(llm_calls.c.output_tokens).label("avg_out"),
            func.percentile_cont(0.9).within_group(llm_calls.c.output_tokens).label("p90_out"),
            func.avg(llm_calls.c.reasoning_tokens).label("avg_reasoning"), func.avg(llm_calls.c.cost_usd).label("avg_cost"),
            func.sum(llm_calls.c.cost_usd).label("cost"), func.sum(llm_calls.c.input_tokens + llm_calls.c.output_tokens).label("tokens"),
            func.sum(llm_calls.c.cached_input_tokens).label("cached"), func.sum(llm_calls.c.input_tokens).label("in_total"),
        ).where(cond))).first()
    n = int(r.n or 0)
    return {"calls": n, "avg_input_tokens": round(float(r.avg_in or 0)), "avg_output_tokens": round(float(r.avg_out or 0)),
            "p90_output_tokens": round(float(r.p90_out or 0)), "avg_reasoning_tokens": round(float(r.avg_reasoning or 0)),
            "avg_cost_usd": float(r.avg_cost or 0), "usd_per_token": float(r.cost or 0) / float(r.tokens) if r.tokens else None,
            "cache_hit_ratio": round(float(r.cached or 0) / float(r.in_total), 3) if r.in_total else 0.0}


def _usd(model: str, tin: int, tout: int, cached_ratio: float, hist: dict[str, Any]) -> float | None:
    c = usage.table_cost(model, tin, int(tin * cached_ratio), tout)
    if c is None and hist.get("usd_per_token"):
        c = (tin + tout) * hist["usd_per_token"]
    return c


async def estimate(org_id: uuid.UUID, operation: str, *, requested: str | None = None, preference: str | None = None,
                   input_tokens: int | None = None, input_text: str | None = None) -> dict[str, Any]:
    r = route(operation, requested, preference)
    t = task(operation)
    hist = await history(org_id, operation, r.model)
    learned = hist["calls"] >= MIN_HISTORY
    if input_text is not None:
        tin = count_tokens(input_text) + SYSTEM_PROMPT_TOKENS + t.evidence_tokens
        in_basis = "counted"
    elif input_tokens is not None:
        tin, in_basis = input_tokens, "counted"
    elif learned:
        tin, in_basis = hist["avg_input_tokens"], "history"
    else:
        tin, in_basis = SYSTEM_PROMPT_TOKENS + t.evidence_tokens, "profile"
    out_expected = hist["avg_output_tokens"] if learned else t.expected_output_tokens
    out_high = min(t.max_output_tokens, max(hist["p90_output_tokens"], out_expected) if learned else round(out_expected * 1.8))
    cached = hist["cache_hit_ratio"] if learned else 0.0
    exp_usd, high_usd, max_usd = (_usd(r.model, tin, o, cached, hist) for o in (out_expected, out_high, t.max_output_tokens))
    return {"operation": operation, "purpose": t.purpose, **asdict(r),
            "input_tokens": tin, "output_tokens": {"expected": out_expected, "high": out_high, "max": t.max_output_tokens},
            "cost_usd": {"expected": exp_usd, "high": high_usd, "max": max_usd}, "priced": exp_usd is not None,
            "basis": {"input": in_basis, "output": f"history ({hist['calls']} calls, {HISTORY_DAYS}d)" if learned else "profile default"},
            "history": hist}


async def routing_table(org_id: uuid.UUID) -> list[dict[str, Any]]:
    out = []
    prices = usage.prices()
    for op, t in sorted(tasks().items(), key=lambda kv: (EFFORTS.index(kv[1].reasoning_effort) * -1, kv[0])):
        r = route(op)
        hist = await history(org_id, op, r.model)
        p = prices.get(r.model)
        out.append({"operation": op, "purpose": t.purpose, "model": r.model, "configured_model": t.model, "reasoning_effort": t.reasoning_effort,
                    "max_output_tokens": t.max_output_tokens, "user_selectable": t.user_selectable,
                    "price": {"input_per_1m": p.input, "cached_input_per_1m": p.cached, "output_per_1m": p.output} if p else None,
                    "estimate": (await estimate(org_id, op))["cost_usd"], "history": hist})
    return out

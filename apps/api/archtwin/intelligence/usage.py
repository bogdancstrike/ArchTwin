"""LLM usage ledger, prices and monthly spend limits (cost control for the OpenAI key behind LiteLLM).

* Prices: USD per 1M tokens (input, cached input, output). Defaults are the reviewed list prices for the models we know;
  override or add models with ARCHTWIN_LLM_PRICES='{"gpt-6-sol": [in, cached, out]}'. A model without a price is
  "unpriced": its cost comes from LiteLLM (`x-litellm-response-cost`) and the UI says so.
* Cost of a call is decided in ONE place (`resolve_cost`): LiteLLM's figure when present and within 0.5x-2.5x of the
  table (else the table wins and a mismatch is logged), the table when LiteLLM gives none.
* `llm_calls` is append-only: every call (ok or error) is one row; every total is a SUM over it, never a counter.
* Spend limits (`spend_limits`): monthly USD caps for `global`, `user:<id>`, `project:<id>`; checked before every call
  (HTTP 402 AT-BUD-001). A cap of 0 blocks all calls for that subject. Limits/spend are cached 30 s per process.
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select, text

from archtwin.common.db import RequestContext, rows, unscoped
from archtwin.common.errors import problem
from archtwin.common.ids import new_id
from archtwin.common.logging import log
from archtwin.common.schema import llm_calls, spend_limits

WARN_AT = 0.8
CACHE_S = 30.0


@dataclass(frozen=True)
class Price:
    input: float
    cached: float
    output: float


DEFAULT_PRICES: dict[str, Price] = {          # USD / 1M tokens (OpenAI list prices, as mirrored in the Horizon stack)
    "gpt-6-luna": Price(0.10, 0.01, 0.50),
    "gpt-5.6-luna": Price(0.20, 0.02, 1.20),
    "text-embedding-3-large": Price(0.13, 0.13, 0.0),
}


def prices() -> dict[str, Price]:
    t = dict(DEFAULT_PRICES)
    raw = os.environ.get("ARCHTWIN_LLM_PRICES", "")
    if raw:
        try:
            for k, v in json.loads(raw).items():
                i, c, o = (list(v) + [None, None, None])[:3]
                t[str(k)] = Price(float(i), float(c if c is not None else i), float(o if o is not None else 0))
        except (ValueError, TypeError) as e:
            log.warning("llm_prices_invalid", error=str(e)[:200])
    return t


def price_table() -> list[dict[str, Any]]:
    from archtwin.intelligence import gateway
    t = prices()
    names = sorted(set(t) | {m["alias"] for m in gateway.selectable()})
    return [{"model": m, "priced": m in t, "input_per_1m": t[m].input if m in t else None, "cached_input_per_1m": t[m].cached if m in t else None,
             "output_per_1m": t[m].output if m in t else None,
             "source": ("ARCHTWIN_LLM_PRICES" if m not in DEFAULT_PRICES else "default") if m in t else "LiteLLM-reported cost"} for m in names]


def table_cost(model: str, input_tokens: int, cached: int, output_tokens: int) -> float | None:
    p = prices().get(model)
    if p is None:
        return None
    cached = max(0, min(cached, input_tokens))
    return ((input_tokens - cached) * p.input + cached * p.cached + output_tokens * p.output) / 1_000_000


def resolve_cost(model: str, input_tokens: int, cached: int, output_tokens: int, gateway_cost: float | None) -> tuple[float, str]:
    ours = table_cost(model, input_tokens, cached, output_tokens)
    gw = gateway_cost if gateway_cost is not None and math.isfinite(gateway_cost) and gateway_cost >= 0 else None
    if ours is None:
        if gw is not None:
            return gw, "litellm"
        log.warning("llm_cost_unpriced", model=model)
        fb = table_cost("gpt-6-luna", input_tokens, cached, output_tokens) or 0.0
        return fb, "fallback-luna"
    if gw is None or ours == 0:
        return ours, "table"
    if 0.5 * ours <= gw <= 2.5 * ours:
        return gw, "litellm"
    log.warning("llm_cost_mismatch", model=model, table=ours, gateway=gw)
    return ours, "table"


async def record(ctx: RequestContext | None, *, org_id: uuid.UUID, project_id: uuid.UUID | None, user_id: uuid.UUID | None,
                 operation: str, model: str, input_tokens: int = 0, cached_input_tokens: int = 0, output_tokens: int = 0,
                 reasoning_tokens: int = 0, gateway_cost: float | None = None, latency_ms: int = 0, status: str = "ok",
                 error_code: str | None = None, trace_id: str = "") -> float:
    cost, src = resolve_cost(model, input_tokens, cached_input_tokens, output_tokens, gateway_cost) if status == "ok" else (0.0, "none")
    async with unscoped() as conn:                    # the ledger is org-scoped; set the org for RLS explicitly
        await conn.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": str(org_id)})
        await conn.execute(llm_calls.insert().values(
            id=new_id(), org_id=org_id, project_id=project_id, user_id=user_id, operation=operation, model=model,
            input_tokens=input_tokens, cached_input_tokens=cached_input_tokens, output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens, cost_usd=Decimal(str(round(cost, 6))), cost_source=src, latency_ms=latency_ms,
            status=status, error_code=error_code, trace_id=trace_id[:200]))
    _CACHE.pop(str(org_id), None)
    return cost


# ------------------------------------------------------------------ spend limits
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def month_start(now: datetime | None = None) -> datetime:
    n = now or datetime.now(UTC)
    return n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _org_state(org_id: uuid.UUID) -> dict[str, Any]:
    hit = _CACHE.get(str(org_id))
    if hit and time.monotonic() - hit[0] < CACHE_S:
        return hit[1]
    async with unscoped() as conn:
        await conn.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": str(org_id)})
        lim = {r["subject"]: float(r["monthly_usd"]) for r in rows(await conn.execute(
            select(spend_limits.c.subject, spend_limits.c.monthly_usd).where(spend_limits.c.org_id == org_id)))}
        since = month_start()
        base = and_(llm_calls.c.org_id == org_id, llm_calls.c.created_at >= since)
        total = float((await conn.execute(select(func.coalesce(func.sum(llm_calls.c.cost_usd), 0)).where(base))).scalar() or 0)
        by_user = {str(r["k"]): float(r["v"]) for r in rows(await conn.execute(
            select(llm_calls.c.user_id.label("k"), func.sum(llm_calls.c.cost_usd).label("v")).where(and_(base, llm_calls.c.user_id.isnot(None)))
            .group_by(llm_calls.c.user_id)))}
        by_project = {str(r["k"]): float(r["v"]) for r in rows(await conn.execute(
            select(llm_calls.c.project_id.label("k"), func.sum(llm_calls.c.cost_usd).label("v")).where(and_(base, llm_calls.c.project_id.isnot(None)))
            .group_by(llm_calls.c.project_id)))}
    state = {"limits": lim, "spent": {"global": total, **{f"user:{k}": v for k, v in by_user.items()},
                                      **{f"project:{k}": v for k, v in by_project.items()}}}
    _CACHE[str(org_id)] = (time.monotonic(), state)
    return state


def invalidate(org_id: uuid.UUID) -> None:
    _CACHE.pop(str(org_id), None)


async def check(ctx: RequestContext) -> list[dict[str, Any]]:
    """Raise 402 when any applicable monthly cap is reached; return the applicable caps (for warnings in the UI)."""
    st = await _org_state(ctx.org_id)
    subjects = ["global", f"user:{ctx.actor_id}"] + ([f"project:{ctx.project_id}"] if ctx.project_id else [])
    out = []
    for s in subjects:
        if s not in st["limits"]:
            continue
        cap, spent = st["limits"][s], st["spent"].get(s, 0.0)
        out.append({"subject": s, "limit_usd": cap, "spent_usd": round(spent, 6), "pct": round(spent / cap, 4) if cap else 1.0})
        if spent >= cap:
            raise problem(402, "AT-BUD-001", "Spend limit reached",
                          f"The monthly AI spend limit for {s.split(':')[0]} (${cap:.2f}) is reached; an administrator can raise it.")
    return out


async def list_limits(ctx: RequestContext) -> list[dict[str, Any]]:
    st = await _org_state(ctx.org_id)
    return [{"subject": s, "monthly_usd": v, "spent_usd": round(st["spent"].get(s, 0.0), 6),
             "pct": round(st["spent"].get(s, 0.0) / v, 4) if v else 1.0} for s, v in sorted(st["limits"].items())]

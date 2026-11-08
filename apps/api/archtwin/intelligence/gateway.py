"""AI gateway (AT-LLM_GATEWAY-001..005, ADR-0005). The ONLY place that talks to a model, always through LiteLLM.

- Model aliases are validated server-side against MODEL_PROFILES.yaml (gpt-6-luna default, gpt-6-terra, gpt-6-sol).
- Retries happen in exactly one layer: here (LiteLLM has num_retries: 0).
- Langfuse tracing happens in LiteLLM (callback); we pass non-sensitive metadata only (ids, operation).
- ARCHTWIN_LLM_MODE=fake gives deterministic zero-token responses for CI.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from openai import (APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, InternalServerError, NotFoundError,
                    PermissionDeniedError, RateLimitError)

from archtwin.common.errors import problem
from archtwin.config import settings


@lru_cache
def profiles() -> dict[str, Any]:
    return yaml.safe_load((Path(__file__).parent / "MODEL_PROFILES.yaml").read_text())


def selectable() -> list[dict[str, Any]]:
    return profiles()["selectable_models"]["options"]


def default_model() -> str:
    return profiles()["selectable_models"]["default"]


# Capability validation: a model the provider rejects is hidden, not degraded (MODEL_PROFILES.yaml note).
_unavailable: dict[str, float] = {}
UNAVAILABLE_TTL_S = 3600


def mark_unavailable(alias: str) -> None:
    _unavailable[alias] = time.monotonic()


def is_available(alias: str) -> bool:
    t = _unavailable.get(alias)
    return t is None or time.monotonic() - t > UNAVAILABLE_TTL_S


def available() -> list[dict[str, Any]]:
    return [o for o in selectable() if is_available(o["alias"])]


async def probe_models() -> dict[str, bool]:
    """1-token probe per selectable alias through LiteLLM (skipped in fake mode)."""
    if settings().llm_mode == "fake":
        return {o["alias"]: True for o in selectable()}
    out = {}
    for o in selectable():
        try:
            await _llm().chat.completions.create(model=o["alias"], messages=[{"role": "user", "content": "ping"}],
                                                 max_completion_tokens=16, extra_body={"metadata": {"trace_name": "archtwin.capability_probe"}})
            out[o["alias"]] = True
        except (NotFoundError, PermissionDeniedError):
            mark_unavailable(o["alias"])
            out[o["alias"]] = False
        except Exception:  # noqa: BLE001 — transient: do not hide
            out[o["alias"]] = True
    return out


def resolve_model(requested: str | None, preference: str | None, allowlist: list[str] | None = None) -> str:
    allowed = [o["alias"] for o in selectable() if (not allowlist or o["alias"] in allowlist) and is_available(o["alias"])]
    if not allowed:
        raise problem(503, "AT-AI-003", "No model available", "None of the selectable models passed capability validation.", retryable=True)
    for cand in (requested, preference):
        if cand:
            if cand not in allowed:
                if cand is requested:
                    raise problem(422, "AT-AI-001", "Model not allowed", f"{cand!r} is not a selectable model here. Allowed: {', '.join(allowed)}")
                continue
            return cand
    return default_model() if default_model() in allowed else allowed[0]


@dataclass
class Completion:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    trace_id: str


_client: AsyncOpenAI | None = None


def _llm() -> AsyncOpenAI:
    global _client
    if _client is None:
        s = settings()
        _client = AsyncOpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key or "none", timeout=s.llm_timeout_s, max_retries=0)
    return _client


def _fake(messages: list[dict[str, str]], json_mode: bool) -> str:
    user = messages[-1]["content"]
    ids = []
    for line in user.splitlines():
        if line.startswith("[E") and "]" in line:
            ids.append(line[1:line.index("]")])
    cites = " ".join(f"[{i}]" for i in ids[:3])
    if json_mode:
        return json.dumps({"title": "Adopt the observed integration pattern", "context": f"Drafted from evidence {cites}.",
                           "decision_drivers": ["consistency with observed architecture"],
                           "considered_options": [{"name": "Option A: synchronous HTTP", "pros": ["simple"], "cons": ["coupling"]},
                                                  {"name": "Option B: asynchronous via workflow engine", "pros": ["resilience"], "cons": ["complexity"]}],
                           "decision_outcome": "Option B, because it matches existing durable-work patterns " + cites,
                           "consequences": "More moving parts; better failure isolation.", "citations": ids[:3]})
    if not ids:
        return "I don't have evidence in this project to answer that. The answer is UNKNOWN until a connector covers it."
    return f"Based on the project's evidence, the relevant elements are listed in the cited sources {cites}. (fake LLM mode)"


async def complete(messages: list[dict[str, str]], *, model: str, operation: str, project_id: str, user_id: str,
                   json_mode: bool = False, max_tokens: int = 4000) -> Completion:
    t0 = time.monotonic()
    if settings().llm_mode == "fake":
        txt = _fake(messages, json_mode)
        return Completion(txt, model, sum(len(m["content"]) // 4 for m in messages), len(txt) // 4, int((time.monotonic() - t0) * 1000), "fake")
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "max_completion_tokens": max_tokens,
                              "extra_body": {"reasoning_effort": "medium",
                                             "metadata": {"trace_name": f"archtwin.{operation}", "generation_name": operation,
                                                          "trace_user_id": user_id, "session_id": f"project-{project_id}",
                                                          "tags": [f"project:{project_id}", f"op:{operation}"]}}}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    last: Exception | None = None
    for attempt in range(3):                      # the single retry layer
        try:
            r = await _llm().chat.completions.create(**kwargs)
            u = r.usage
            return Completion(r.choices[0].message.content or "", r.model or model, getattr(u, "prompt_tokens", 0) or 0,
                              getattr(u, "completion_tokens", 0) or 0, int((time.monotonic() - t0) * 1000), r.id or "")
        except (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError) as e:
            last = e
            await asyncio.sleep(1.5 * (attempt + 1))
        except (NotFoundError, PermissionDeniedError) as e:
            mark_unavailable(model)
            raise problem(422, "AT-AI-004", "Model unavailable", f"{model} failed capability validation with the provider and is now hidden; "
                          "choose another model.") from e
        except APIStatusError as e:
            raise problem(502, "AT-AI-005", "AI provider error", f"HTTP {e.status_code}", retryable=e.status_code >= 500) from e
    raise problem(503, "AT-AI-002", "AI gateway unavailable", type(last).__name__ if last else "", retryable=True)

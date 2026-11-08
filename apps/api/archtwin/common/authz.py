"""Cerbos authorization (AT-IDENTITY_POLICY-002/003).

- `require()` / `allowed()` use CheckResources for commands and single reads.
- `plan_filter()` uses PlanResources and the official cerbos-sqlalchemy adapter to turn the plan into a SQL WHERE clause
  for list endpoints. Any adapter error (unknown operator, unmapped attribute) ⇒ DENY (fail closed). PDP unreachable ⇒ 503.
"""
from __future__ import annotations

from typing import Any

import httpx
from cerbos.sdk.model import PlanResourcesResponse
from cerbos_sqlalchemy import get_query
from sqlalchemy import false, true

from archtwin.common.db import Principal
from archtwin.common.errors import problem
from archtwin.common.logging import log
from archtwin.config import settings

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=settings().cerbos_url, timeout=3)
    return _client


def _principal(p: Principal) -> dict[str, Any]:
    return p.cerbos()


async def check(p: Principal, kind: str, rid: str, attr: dict[str, Any], actions: list[str]) -> dict[str, bool]:
    body = {"requestId": "archtwin", "principal": _principal(p),
            "resources": [{"actions": actions, "resource": {"kind": kind, "id": rid or "new",
                                                           "attr": {k: (str(v) if v is not None and not isinstance(v, bool | int | float | list) else v)
                                                                    for k, v in attr.items()}}}]}
    try:
        r = await _http().post("/api/check/resources", json=body)
        r.raise_for_status()
        res = r.json()["results"][0]["actions"]
    except Exception as e:
        log.error("cerbos_unavailable", error=type(e).__name__)
        raise problem(503, "AT-AUTHZ-002", "Authorization service unavailable", retryable=True) from e
    return {a: res.get(a) == "EFFECT_ALLOW" for a in actions}


async def allowed(p: Principal, kind: str, action: str, rid: str = "", attr: dict | None = None) -> bool:
    return (await check(p, kind, rid, attr or {}, [action]))[action]


async def plan(p: Principal, kind: str, action: str) -> PlanResourcesResponse:
    body = {"requestId": "archtwin-plan", "action": action, "principal": _principal(p),
            "resource": {"kind": kind, "attr": {}, "policyVersion": "default"}}
    try:
        r = await _http().post("/api/plan/resources", json=body)
        r.raise_for_status()
        data = r.json()
        if "actions" in data and "action" not in data:
            data["action"] = data["actions"]
        data.setdefault("policyVersion", "default")          # omitted by some Cerbos versions
        return PlanResourcesResponse.from_dict(data)
    except Exception as e:
        log.error("cerbos_plan_unavailable", error=type(e).__name__)
        raise problem(503, "AT-AUTHZ-002", "Authorization service unavailable", retryable=True) from e


def plan_to_where(plan_resp: PlanResourcesResponse, table, attr_map: dict[str, Any]):
    """Translate a query plan into a WHERE expression; any failure ⇒ false() (deny)."""
    try:
        q = get_query(plan_resp, table, attr_map)
    except Exception as e:  # noqa: BLE001  — unknown operator / unmapped attribute
        log.warning("cerbos_plan_untranslatable_denied", error=str(e)[:200])
        return false()
    wc = q.whereclause
    return true() if wc is None else wc


async def plan_filter(p: Principal, kind: str, action: str, table, attr_map: dict[str, Any]):
    return plan_to_where(await plan(p, kind, action), table, attr_map)


async def healthy() -> bool:
    try:
        return (await _http().get("/_cerbos/health")).status_code == 200
    except Exception:  # noqa: BLE001
        return False

"""Feature flags (AT-FEATURE_FLAGS-001..003, design D8).

Typed catalog in `catalog.yaml` (generated from docs/feature-flags/FLAG_CATALOG.md); overrides in PostgreSQL; evaluated
through the OpenFeature API with `PostgresFlagProvider`. Precedence:
  security invariant (always ON) > emergency kill switch > enforced org policy > project override > org override > default
Cache TTL is 5 s (propagation target < 15 s). Checked in the API (`require_flag`) and again when a queued job starts.
"""
from __future__ import annotations

import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from openfeature import api as of_api
from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails, Reason
from openfeature.provider import AbstractProvider
from openfeature.provider.metadata import Metadata
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from archtwin.common.db import RequestContext, rows, unscoped
from archtwin.common.errors import problem
from archtwin.common.ids import new_id
from archtwin.common.schema import flag_overrides

CACHE_TTL_S = 5.0
KILL_SWITCH = "security.emergency_kill_switch"


@lru_cache
def catalog() -> dict[str, dict[str, Any]]:
    data = yaml.safe_load((Path(__file__).parent / "catalog.yaml").read_text())
    return {f["key"]: f for f in data["flags"]}


def is_registered(key: str) -> bool:
    return key in catalog()


class _Cache:
    def __init__(self) -> None:
        self.overrides: list[dict[str, Any]] = []
        self.loaded_at = 0.0

    async def refresh(self, force: bool = False) -> None:
        if force or time.monotonic() - self.loaded_at > CACHE_TTL_S:
            async with unscoped() as conn:
                self.overrides = rows(await conn.execute(select(flag_overrides)))
            self.loaded_at = time.monotonic()


cache = _Cache()


def evaluate(key: str, org_id: str | None, project_id: str | None, overrides: list[dict[str, Any]]) -> tuple[bool, str]:
    """Pure precedence function (unit-tested truth table). Returns (value, reason)."""
    meta = catalog().get(key)
    if meta is None:
        return False, "unregistered"                       # unknown flags are OFF (fail closed)
    if meta["immutable"]:
        return True, "security_invariant"

    def ov(k: str, kind: str, sid: str | None):
        if sid is None and kind != "global":
            return None
        for o in overrides:
            if o["flag_key"] == k and o["scope_kind"] == kind and o["scope_id"] == (sid or ""):
                return o
        return None

    if key != KILL_SWITCH:
        for kind, sid in (("global", None), ("org", org_id), ("project", project_id)):
            k = ov(KILL_SWITCH, kind, sid)
            if k and k["value"]:
                return False, f"emergency_off:{kind}"
    org_o = ov(key, "org", org_id)
    if org_o and org_o["enforce"]:
        return bool(org_o["value"]), "org_policy"
    proj_o = ov(key, "project", project_id)
    if proj_o:
        return bool(proj_o["value"]), "project_override"
    if org_o:
        return bool(org_o["value"]), "org_override"
    glob = ov(key, "global", None)
    if glob:
        return bool(glob["value"]), "global_override"
    return bool(meta["default"]), "default"


class PostgresFlagProvider(AbstractProvider):
    def get_metadata(self) -> Metadata:
        return Metadata(name="archtwin-postgres")

    def resolve_boolean_details(self, flag_key: str, default_value: bool, evaluation_context: EvaluationContext | None = None):
        attrs = (evaluation_context.attributes if evaluation_context else {}) or {}
        value, reason = evaluate(flag_key, attrs.get("org_id"), attrs.get("project_id"), cache.overrides)
        return FlagResolutionDetails(value=value, reason=Reason.TARGETING_MATCH if reason != "default" else Reason.DEFAULT,
                                     flag_metadata={"archtwin_reason": reason})

    def _unsupported(self, flag_key, default_value, evaluation_context=None):
        return FlagResolutionDetails(value=default_value, reason=Reason.DEFAULT)

    resolve_string_details = resolve_integer_details = resolve_float_details = resolve_object_details = _unsupported


of_api.set_provider(PostgresFlagProvider())
_client = of_api.get_client("archtwin")


async def enabled(key: str, org_id: uuid.UUID | str | None, project_id: uuid.UUID | str | None = None) -> bool:
    if not is_registered(key):
        raise RuntimeError(f"flag {key!r} is not registered in the catalog")
    await cache.refresh()
    ctx = EvaluationContext(targeting_key=str(org_id or ""), attributes={
        "org_id": str(org_id) if org_id else None, "project_id": str(project_id) if project_id else None})
    return _client.get_boolean_value(key, False, ctx)


async def require(ctx: RequestContext, *keys: str) -> None:
    for k in keys:
        if not await enabled(k, ctx.org_id, ctx.project_id):
            raise problem(404, "AT-FEATURE-DISABLED", "Feature disabled", f"'{k}' is not enabled for this scope.",
                          extra={"flag": k})


async def list_flags(org_id: uuid.UUID, project_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    await cache.refresh(force=True)
    out = []
    for key, meta in catalog().items():
        value, reason = evaluate(key, str(org_id), str(project_id) if project_id else None, cache.overrides)
        mine = [o for o in cache.overrides if o["flag_key"] == key and (
            o["scope_kind"] == "global" or (o["scope_kind"] == "org" and o["scope_id"] == str(org_id))
            or (project_id and o["scope_kind"] == "project" and o["scope_id"] == str(project_id)))]
        out.append({**meta, "value": value, "reason": reason,
                    "overrides": [{k: o[k] for k in ("scope_kind", "scope_id", "value", "enforce", "reason", "updated_at")} for o in mine]})
    return out


async def set_override(key: str, scope_kind: str, scope_id: str, value: bool, *, enforce: bool = False, reason: str = "",
                       actor: uuid.UUID | None = None) -> None:
    meta = catalog().get(key)
    if meta is None:
        raise problem(422, "AT-FLAG-001", "Unknown flag", key)
    if meta["immutable"]:
        raise problem(409, "AT-FLAG-002", "Security invariant", f"{key} cannot be changed.")
    if scope_kind not in ("org", "project"):
        raise problem(422, "AT-FLAG-003", "Invalid scope", scope_kind)
    async with unscoped() as conn:
        await conn.execute(pg_insert(flag_overrides).values(
            id=new_id(), flag_key=key, scope_kind=scope_kind, scope_id=scope_id, value=value, enforce=enforce,
            reason=reason, updated_by=actor).on_conflict_do_update(
            index_elements=["flag_key", "scope_kind", "scope_id"],
            set_={"value": value, "enforce": enforce, "reason": reason, "updated_by": actor, "updated_at": __import__("sqlalchemy").func.now()}))
    await cache.refresh(force=True)

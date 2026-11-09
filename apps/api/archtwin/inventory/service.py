"""Inventory: observations and freshness (AT-NORMALIZATION_FRESHNESS-002/003). Freshness is computed in ONE place."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, select

from archtwin.common.db import RequestContext, rows, uow
from archtwin.common.schema import connectors, observations, scan_runs


def freshness(c: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """current | stale | incomplete | unknown. Missing or old evidence is never treated as absence."""
    now = now or datetime.now(UTC)
    if not c.get("enabled", True):
        return {"status": "unknown", "reason": "connector disabled"}
    last_complete, status = c.get("last_complete_at"), c.get("last_status")
    if not last_complete:
        return {"status": "incomplete" if status == "partial" else "unknown",
                "reason": "no complete scan yet" if status != "failed" else "last scan failed"}
    age = (now - last_complete).total_seconds()
    if age > c.get("freshness_sla_s", 86400):
        return {"status": "stale", "reason": f"last complete scan {int(age // 60)} min ago exceeds SLA", "age_s": int(age)}
    if status == "partial":
        return {"status": "incomplete", "reason": "latest scan was partial", "age_s": int(age)}
    if status == "failed":
        return {"status": "stale", "reason": "latest scan failed; showing last complete evidence", "age_s": int(age)}
    return {"status": "current", "age_s": int(age)}


async def summary(ctx: RequestContext) -> dict[str, Any]:
    async with uow(ctx) as conn:
        cs = rows(await conn.execute(select(connectors).where(connectors.c.project_id == ctx.project_id)))
        counts = rows(await conn.execute(select(observations.c.origin, observations.c.kind, func.count().label("n"))
                                         .where(observations.c.project_id == ctx.project_id)
                                         .group_by(observations.c.origin, observations.c.kind)))
    return {"connectors": [{"id": c["id"], "name": c["name"], "kind": c["kind"], "freshness": freshness(c)} for c in cs],
            "observation_counts": counts}


async def observations_for(ctx: RequestContext, subject_key: str, limit: int = 50) -> list[dict[str, Any]]:
    async with uow(ctx) as conn:
        return rows(await conn.execute(select(observations).where(and_(observations.c.project_id == ctx.project_id,
                                                                       observations.c.subject_key == subject_key))
                                       .order_by(observations.c.observed_at.desc()).limit(limit)))


async def latest_inputs(conn, ctx: RequestContext) -> list[dict[str, Any]]:
    """Per connector: its latest COMPLETE scan, plus newer partial scans (additive only — partial never tombstones)."""
    cs = rows(await conn.execute(select(connectors).where(connectors.c.project_id == ctx.project_id)))
    out = []
    for c in cs:
        scans = rows(await conn.execute(select(scan_runs.c.id, scan_runs.c.status, scan_runs.c.finished_at, scan_runs.c.coverage,
                                               scan_runs.c.revision)
                                        .where(and_(scan_runs.c.connector_id == c["id"], scan_runs.c.status.in_(["complete", "partial"])))
                                        .order_by(scan_runs.c.finished_at.desc()).limit(20)))
        chosen = []
        for s in scans:
            chosen.append(s)
            if s["status"] == "complete":
                break
        if chosen:
            out.append({"connector": c, "scans": chosen, "freshness": freshness(c)})
    return out

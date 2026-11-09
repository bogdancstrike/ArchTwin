"""Activities: system-scoped RequestContext per job; flags are re-checked when the job starts (AT-FEATURE_FLAGS-003)."""
from __future__ import annotations

import uuid

from temporalio import activity

from archtwin.architecture import service as arch
from archtwin.common.db import RequestContext
from archtwin.connectors import service as connectors
from archtwin.drift import service as drift
from archtwin.flags import service as flags


def _ctx(org_id: str, project_id: str) -> RequestContext:
    return RequestContext(None, uuid.UUID(org_id), uuid.UUID(project_id), trace_id=activity.info().workflow_id, system=True)


@activity.defn(name="run_scan")
async def run_scan(org_id: str, project_id: str, scan_id: str) -> dict:
    return await connectors.execute_scan(_ctx(org_id, project_id), uuid.UUID(scan_id))


@activity.defn(name="build_snapshot")
async def build_snapshot(org_id: str, project_id: str) -> dict:
    ctx = _ctx(org_id, project_id)
    if not await flags.enabled("module.architecture-graph", ctx.org_id, ctx.project_id):
        return {"skipped": "module.architecture-graph off"}
    s = await arch.build_snapshot(ctx)
    return {"snapshot_id": str(s["id"]), "version": s["version"], "created": s["created"]}


@activity.defn(name="evaluate_drift")
async def evaluate_drift(org_id: str, project_id: str) -> dict:
    ctx = _ctx(org_id, project_id)
    if not await flags.enabled("module.drift-engine", ctx.org_id, ctx.project_id):
        return {"skipped": "module.drift-engine off"}
    return await drift.evaluate(ctx)


ALL = [run_scan, build_snapshot, evaluate_drift]

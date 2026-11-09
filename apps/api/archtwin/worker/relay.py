"""Outbox relay: claims pending events (SKIP LOCKED), dispatches to Temporal, retries with backoff, dead-letters."""
from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
from sqlalchemy import select, text
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from archtwin.common.db import RequestContext, rows, unscoped
from archtwin.common.logging import log
from archtwin.common.schema import connectors, projects
from archtwin.config import settings
from archtwin.flags import service as flags
from archtwin.kernel import outbox
from archtwin.worker.workflows import DriftWorkflow, GraphBuildWorkflow, ScanWorkflow


async def dispatch(client: Client, ev: dict) -> None:
    kind, org, proj, p = ev["event_kind"], str(ev["org_id"]), str(ev["project_id"]) if ev["project_id"] else None, ev["payload"]
    q = settings().task_queue
    if kind == "connector.scan_requested":
        try:
            await client.start_workflow(ScanWorkflow.run, args=[org, proj, p["scan_id"]], id=f"scan-{p['scan_id']}", task_queue=q)
        except WorkflowAlreadyStartedError:
            pass                                    # redelivery: applied once
    elif kind == "inventory.changed":
        await client.start_workflow(GraphBuildWorkflow.run, args=[org, proj, settings().graph_debounce_s], id=f"graph-{proj}",
                                    task_queue=q, start_signal="touch",
                                    id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE)
    elif kind in ("architecture.snapshot_created", "architecture.baseline_approved"):
        if await flags.enabled("module.drift-engine", org, proj) and await flags.enabled("module.continuous-watchers", org, proj):
            with contextlib.suppress(WorkflowAlreadyStartedError):
                await client.start_workflow(DriftWorkflow.run, args=[org, proj], id=f"drift-{proj}-{ev['id']}", task_queue=q)


async def drain(client: Client) -> int:
    n = 0
    while True:
        async with unscoped() as conn:
            batch = await outbox.claim(conn, 20)
            for ev in batch:
                try:
                    await dispatch(client, ev)
                    await outbox.mark_delivered(conn, ev["id"])
                except Exception as e:  # noqa: BLE001
                    log.warning("outbox_dispatch_failed", event=ev["event_kind"], error=str(e)[:200])
                    await outbox.mark_failed(conn, ev, str(e))
        n += len(batch)
        if len(batch) < 20:
            return n


async def run_relay(client: Client, stop: asyncio.Event) -> None:
    dsn = settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    wake = asyncio.Event()
    conn = await asyncpg.connect(dsn)
    await conn.add_listener(outbox.CHANNEL, lambda *_: wake.set())
    log.info("outbox_relay_started")
    try:
        while not stop.is_set():
            try:
                await drain(client)
            except Exception as e:  # noqa: BLE001
                log.error("outbox_relay_error", error=str(e)[:300])
            wake.clear()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(wake.wait(), timeout=5)
    finally:
        await conn.close()


async def reconcile_loop(stop: asyncio.Event, interval_s: int = 300) -> None:
    """Scheduled reconcile: connectors past ~80% of their freshness SLA get a new scan (flag connectors.full_reconciliation)."""
    from archtwin.connectors import service as csvc
    while not stop.is_set():
        try:
            async with unscoped() as conn:
                prj = rows(await conn.execute(select(projects.c.id, projects.c.org_id)))
            for p in prj:
                if not await flags.enabled("connectors.full_reconciliation", p["org_id"], p["id"]):
                    continue
                ctx = RequestContext(None, p["org_id"], p["id"], "reconcile", True)
                from archtwin.common.db import uow
                async with uow(ctx) as conn:
                    cs = rows(await conn.execute(select(connectors).where(connectors.c.enabled.is_(True))))
                    running = {r.connector_id for r in (await conn.execute(text(
                        "SELECT connector_id FROM scan_runs WHERE status IN ('queued','running') AND created_at > now() - interval '1 hour'"))).all()}
                now = datetime.now(UTC)
                for c in cs:
                    due = not c["last_success_at"] or now - c["last_success_at"] > timedelta(seconds=c["freshness_sla_s"] * 0.8)
                    if due and c["id"] not in running:
                        await csvc.request_scan(ctx, c["id"], None)
                        log.info("reconcile_scan_requested", connector=str(c["id"]))
        except Exception as e:  # noqa: BLE001
            log.error("reconcile_error", error=str(e)[:300])
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval_s)

_ = uuid

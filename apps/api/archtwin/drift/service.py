"""Drift evaluation, triage, suppressions and accept-as-intended (AT-DRIFT_ENGINE-003/004, AT-DRIFT_TRIAGE)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from archtwin.architecture import service as arch
from archtwin.audit import service as audit
from archtwin.common.db import RequestContext, row, rows, uow
from archtwin.common.errors import not_found, problem
from archtwin.common.ids import new_id
from archtwin.common.paging import PageQuery, paginate_select
from archtwin.common.schema import drift_comments, drift_evaluations, drift_findings, users
from archtwin.drift import rules
from archtwin.kernel import outbox
from archtwin.notifications import service as notify

OPEN = ("new", "acknowledged", "investigating")
STATES = {"new", "acknowledged", "investigating", "accepted", "resolved", "suppressed"}


async def evaluate(ctx: RequestContext) -> dict[str, Any]:
    async with uow(ctx) as conn:
        snap = await arch.resolve_snapshot(conn, ctx)
        if not snap:
            return {"status": "no_snapshot"}
        current = await arch.load_graph(conn, snap["id"])
        base = await arch.current_baseline(conn, ctx)
        baseline_graph = await arch.load_graph(conn, base["snapshot_id"]) if base else None
        cov = rules.Coverage.from_inputs(snap["inputs"].get("scans", []))
        results = rules.evaluate(baseline_graph, current, cov)
        now = datetime.now(UTC)
        seen: set[uuid.UUID] = set()
        counts = {"drift": 0, "unknown": 0, "incomplete": 0, "new": 0, "reopened": 0}
        new_findings = []
        for f in results:
            fid = rules.finding_id(ctx.project_id, f["rule_id"], f["subject_key"])
            seen.add(fid)
            counts[f["verdict"]] += 1
            prev = row((await conn.execute(select(drift_findings).where(drift_findings.c.id == fid))).first())
            values = {**f, "snapshot_id": snap["id"], "baseline_id": base["id"] if base else None, "last_seen": now}
            if prev is None:
                await conn.execute(drift_findings.insert().values(id=fid, org_id=ctx.org_id, project_id=ctx.project_id,
                                                                  first_seen=now, status="new", **values))
                counts["new"] += 1
                if f["verdict"] == "drift":
                    new_findings.append((fid, f))
            else:
                upd = dict(values)
                same_snapshot = prev["snapshot_id"] == snap["id"]
                if not same_snapshot:
                    upd["occurrences"] = prev["occurrences"] + 1
                st = prev["status"]
                if st == "suppressed" and prev["suppressed_until"] and prev["suppressed_until"] < now:
                    upd["status"] = "new"            # expired exception reopens (AT-DRIFT_ENGINE-004)
                    counts["reopened"] += 1
                elif st == "resolved" and not same_snapshot:
                    upd["status"] = "new"            # recurrence reopens
                    counts["reopened"] += 1
                await conn.execute(drift_findings.update().where(drift_findings.c.id == fid).values(**upd, updated_at=now))
        # findings no longer produced: auto-resolve open ones (only drift ones — UNKNOWN never resolves into "fixed")
        stale = rows(await conn.execute(select(drift_findings.c.id, drift_findings.c.status).where(and_(
            drift_findings.c.project_id == ctx.project_id, drift_findings.c.status.in_(OPEN)))))
        resolved = 0
        for s in stale:
            if s["id"] not in seen:
                await conn.execute(drift_findings.update().where(drift_findings.c.id == s["id"]).values(
                    status="resolved", resolution_note="no longer observed in the latest evaluation", updated_at=now))
                resolved += 1
        counts["auto_resolved"] = resolved
        await conn.execute(drift_evaluations.insert().values(id=new_id(), org_id=ctx.org_id, project_id=ctx.project_id,
                                                             baseline_id=base["id"] if base else None, snapshot_id=snap["id"],
                                                             rule_versions={k: v["version"] for k, v in rules.RULES.items()}, counts=counts))
        await audit.record(conn, ctx, "drift.evaluate", "drift_finding", snap["id"], details=counts)
        for fid, f in new_findings[:50]:
            await notify.notify_project(conn, ctx, kind="drift", title=f"{rules.RULES[f['rule_id']]['title']}: {f['subject_key'].split(':', 1)[-1]}",
                                        body=f["title"], link=f"/projects/{ctx.project_id}/drift/{fid}", dedupe_key=f"drift:{fid}")
        if new_findings:
            await outbox.emit(conn, ctx.org_id, ctx.project_id, "drift", snap["id"], "drift.findings_created", {"count": len(new_findings)})
    return {"status": "evaluated", "snapshot": snap["version"], "baseline": bool(base), **counts}


SEVERITY_RANK = func.array_position(["critical", "high", "medium", "low"], drift_findings.c.severity)
FINDING_SORTS = {"severity": SEVERITY_RANK, "last_seen": drift_findings.c.last_seen, "first_seen": drift_findings.c.first_seen,
                 "title": drift_findings.c.title, "status": drift_findings.c.status, "verdict": drift_findings.c.verdict,
                 "occurrences": drift_findings.c.occurrences, "rule": drift_findings.c.rule_id}


def _findings(ctx: RequestContext, status: str | None, verdict: str | None, severity: str | None = None):
    q = select(drift_findings).where(drift_findings.c.project_id == ctx.project_id)
    if status == "open":
        q = q.where(drift_findings.c.status.in_(OPEN))
    elif status:
        q = q.where(drift_findings.c.status == status)
    if verdict:
        q = q.where(drift_findings.c.verdict == verdict)
    if severity:
        q = q.where(drift_findings.c.severity == severity)
    return q


async def list_findings(ctx: RequestContext, status: str | None = None, verdict: str | None = None) -> list[dict[str, Any]]:
    async with uow(ctx) as conn:
        return rows(await conn.execute(_findings(ctx, status, verdict).order_by(SEVERITY_RANK, drift_findings.c.last_seen.desc()).limit(500)))


async def page_findings(ctx: RequestContext, pq: PageQuery, status: str | None = None, verdict: str | None = None,
                        severity: str | None = None) -> dict[str, Any]:
    async with uow(ctx) as conn:
        return await paginate_select(conn, _findings(ctx, status, verdict, severity), pq, sorts=FINDING_SORTS, default_sort="severity",
                                     search=[drift_findings.c.title, drift_findings.c.subject_key, drift_findings.c.rule_id])


async def get_finding(ctx: RequestContext, fid: uuid.UUID) -> dict[str, Any]:
    async with uow(ctx) as conn:
        f = row((await conn.execute(select(drift_findings).where(drift_findings.c.id == fid))).first())
        if not f:
            raise not_found("finding")
        f["comments"] = rows(await conn.execute(select(drift_comments, users.c.username).join(users, users.c.id == drift_comments.c.author_id)
                                                .where(drift_comments.c.finding_id == fid).order_by(drift_comments.c.created_at)))
        f["rule"] = {"id": f["rule_id"], **rules.RULES.get(f["rule_id"], {})}
    return f


async def transition(ctx: RequestContext, fid: uuid.UUID, status: str, note: str = "", suppress_days: int | None = None,
                     assignee: uuid.UUID | None = None) -> dict[str, Any]:
    if status not in STATES:
        raise problem(422, "AT-DRIFT-001", "Unknown status", status)
    if status == "suppressed" and (not note or not suppress_days or suppress_days > 365):
        raise problem(422, "AT-DRIFT-002", "Suppression needs a reason and an expiry (1–365 days)")
    async with uow(ctx) as conn:
        f = row((await conn.execute(select(drift_findings).where(drift_findings.c.id == fid))).first())
        if not f:
            raise not_found("finding")
        upd: dict[str, Any] = {"status": status, "updated_at": datetime.now(UTC)}
        if note:
            upd["resolution_note"] = note
        if status == "suppressed":
            upd["suppressed_until"] = datetime.now(UTC) + __import__("datetime").timedelta(days=suppress_days)
        if assignee:
            upd["assignee_id"] = assignee
        await conn.execute(drift_findings.update().where(drift_findings.c.id == fid).values(**upd))
        if note:
            await conn.execute(drift_comments.insert().values(id=new_id(), org_id=ctx.org_id, project_id=ctx.project_id, finding_id=fid,
                                                              author_id=ctx.actor_id, body=f"[{status}] {note}"))
        await audit.record(conn, ctx, f"drift.{status}", "drift_finding", fid, details={"note": note, "days": suppress_days})
    return await get_finding(ctx, fid)


async def comment(ctx: RequestContext, fid: uuid.UUID, body: str) -> dict[str, Any]:
    async with uow(ctx) as conn:
        if not (await conn.execute(select(drift_findings.c.id).where(drift_findings.c.id == fid))).first():
            raise not_found("finding")
        await conn.execute(drift_comments.insert().values(id=new_id(), org_id=ctx.org_id, project_id=ctx.project_id, finding_id=fid,
                                                          author_id=ctx.actor_id, body=body))
        await audit.record(conn, ctx, "drift.comment", "drift_finding", fid)
    return await get_finding(ctx, fid)


async def open_drift_keys(conn, ctx: RequestContext) -> set[str]:
    rs = await conn.execute(select(drift_findings.c.subject_key).where(and_(
        drift_findings.c.project_id == ctx.project_id, drift_findings.c.status.in_(OPEN), drift_findings.c.verdict == "drift")))
    return {r.subject_key for r in rs}


async def stats(ctx: RequestContext) -> dict[str, Any]:
    async with uow(ctx) as conn:
        rs = rows(await conn.execute(select(drift_findings.c.verdict, drift_findings.c.severity, func.count().label("n"))
                                     .where(and_(drift_findings.c.project_id == ctx.project_id, drift_findings.c.status.in_(OPEN)))
                                     .group_by(drift_findings.c.verdict, drift_findings.c.severity)))
    return {"open": sum(r["n"] for r in rs if r["verdict"] == "drift"), "unknown": sum(r["n"] for r in rs if r["verdict"] != "drift"),
            "by": rs}

_ = pg_insert

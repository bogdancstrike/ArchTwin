"""Snapshots, time travel, diff, baselines and curation (AT-ARCHITECTURE_GRAPH-001..003)."""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from archtwin.architecture import builder
from archtwin.audit import service as audit
from archtwin.common.db import RequestContext, project_lock, row, rows, uow
from archtwin.common.errors import not_found, problem
from archtwin.common.ids import new_id
from archtwin.common.schema import baselines, identity_aliases, identity_suggestions, observations, snapshot_elements, snapshots
from archtwin.inventory.service import latest_inputs
from archtwin.kernel import outbox


async def build_snapshot(ctx: RequestContext, trigger: str = "scan") -> dict[str, Any]:
    """Materialize a new immutable snapshot if the manifest changed (idempotent for unchanged inputs)."""
    async with uow(ctx) as conn:
        await project_lock(conn, ctx.project_id, "snapshot")
        inputs = [i for i in await latest_inputs(conn, ctx) if i["connector"]["enabled"]]
        scan_ids = [s["id"] for i in inputs for s in i["scans"]]
        obs = rows(await conn.execute(select(observations).where(and_(observations.c.project_id == ctx.project_id,
                                                                      observations.c.scan_id.in_(scan_ids))))) if scan_ids else []
        manual = rows(await conn.execute(select(observations).where(and_(observations.c.project_id == ctx.project_id,
                                                                         observations.c.origin == "manual"))))
        aliases = {a.alias_key: a.canonical_key for a in (await conn.execute(select(identity_aliases)
                                                                             .where(identity_aliases.c.project_id == ctx.project_id))).all()}
        g = await asyncio.to_thread(builder.build, obs + manual, aliases)   # CPU-bound: keep the event loop responsive
        last = row((await conn.execute(select(snapshots).where(snapshots.c.project_id == ctx.project_id)
                                       .order_by(snapshots.c.version.desc()).limit(1))).first())
        # coverage is an input to drift (absence vs UNKNOWN): a coverage change is a new snapshot even if the graph is equal
        cov_sig = hashlib.sha256(json.dumps(sorted(
            [str(i["connector"]["id"]), sorted((i["scans"][0]["coverage"] or {}).get("prefixes", [])), i["freshness"]["status"]]
            for i in inputs), default=str).encode()).hexdigest()[:16]
        if last and last["manifest_hash"] == g["manifest_hash"] and last["inputs"].get("coverage_sig") == cov_sig:
            return {**last, "created": False}
        sid = new_id()
        version = (last["version"] + 1) if last else 1
        inp = {"scans": [{"connector_id": str(i["connector"]["id"]), "connector": i["connector"]["name"], "kind": i["connector"]["kind"],
                          "scan_ids": [str(s["id"]) for s in i["scans"]], "revision": i["scans"][0]["revision"],
                          "coverage": i["scans"][0]["coverage"], "freshness": i["freshness"]} for i in inputs],
               "manual_observations": len(manual), "dropped_edges": len(g["dropped_edges"]), "coverage_sig": cov_sig}
        await conn.execute(snapshots.insert().values(id=sid, org_id=ctx.org_id, project_id=ctx.project_id, version=version,
                                                     manifest_hash=g["manifest_hash"], node_count=len(g["nodes"]),
                                                     edge_count=len(g["edges"]), inputs=inp, builder_version=builder.BUILDER_VERSION,
                                                     trigger=trigger))
        batch = [{"snapshot_id": sid, "org_id": ctx.org_id, "project_id": ctx.project_id, "element_kind": "node", "key": k, "data": n}
                 for k, n in g["nodes"].items()] + \
                [{"snapshot_id": sid, "org_id": ctx.org_id, "project_id": ctx.project_id, "element_kind": "edge", "key": k, "data": e}
                 for k, e in g["edges"].items()]
        for i in range(0, len(batch), 500):
            await conn.execute(snapshot_elements.insert(), batch[i:i + 500])
        for a, b, score, reason in builder.suggestions(g["nodes"]):
            await conn.execute(pg_insert(identity_suggestions).values(id=new_id(), org_id=ctx.org_id, project_id=ctx.project_id,
                                                                      key_a=a, key_b=b, score=score, reason=reason).on_conflict_do_nothing())
        await audit.record(conn, ctx, "architecture.snapshot.create", "architecture", sid,
                           details={"version": version, "nodes": len(g["nodes"]), "edges": len(g["edges"])})
        await outbox.emit(conn, ctx.org_id, ctx.project_id, "snapshot", sid, "architecture.snapshot_created",
                          {"snapshot_id": str(sid), "version": version})
        return {**row((await conn.execute(select(snapshots).where(snapshots.c.id == sid))).first()), "created": True}


async def list_snapshots(ctx: RequestContext, limit: int = 100) -> list[dict[str, Any]]:
    async with uow(ctx) as conn:
        return rows(await conn.execute(select(snapshots.c.id, snapshots.c.version, snapshots.c.manifest_hash, snapshots.c.node_count,
                                              snapshots.c.edge_count, snapshots.c.created_at, snapshots.c.trigger, snapshots.c.inputs)
                                       .where(snapshots.c.project_id == ctx.project_id).order_by(snapshots.c.version.desc()).limit(limit)))


async def resolve_snapshot(conn, ctx: RequestContext, snapshot_id: uuid.UUID | None = None, at: datetime | None = None) -> dict | None:
    q = select(snapshots).where(snapshots.c.project_id == ctx.project_id)
    if snapshot_id:
        q = q.where(snapshots.c.id == snapshot_id)
    elif at:
        q = q.where(snapshots.c.created_at <= at)
    return row((await conn.execute(q.order_by(snapshots.c.version.desc()).limit(1))).first())


async def load_graph(conn, snapshot_id: uuid.UUID) -> dict[str, Any]:
    els = (await conn.execute(select(snapshot_elements.c.element_kind, snapshot_elements.c.key, snapshot_elements.c.data)
                              .where(snapshot_elements.c.snapshot_id == snapshot_id))).all()
    return {"nodes": {e.key: e.data for e in els if e.element_kind == "node"},
            "edges": {e.key: e.data for e in els if e.element_kind == "edge"}}


async def graph(ctx: RequestContext, snapshot_id: uuid.UUID | None = None, at: datetime | None = None) -> dict[str, Any]:
    async with uow(ctx) as conn:
        snap = await resolve_snapshot(conn, ctx, snapshot_id, at)
        if not snap:
            return {"snapshot": None, "nodes": {}, "edges": {}}
        g = await load_graph(conn, snap["id"])
        base = row((await conn.execute(select(baselines).where(and_(baselines.c.project_id == ctx.project_id,
                                                                   baselines.c.status == "approved"))
                                       .order_by(baselines.c.decided_at.desc()).limit(1))).first())
    return {"snapshot": snap, "baseline": base, **g}


async def diff_snapshots(ctx: RequestContext, a: uuid.UUID, b: uuid.UUID) -> dict[str, Any]:
    async with uow(ctx) as conn:
        sa, sb = await resolve_snapshot(conn, ctx, a), await resolve_snapshot(conn, ctx, b)
        if not sa or not sb:
            raise not_found("snapshot")
        ga, gb = await load_graph(conn, a), await load_graph(conn, b)
    d = await asyncio.to_thread(builder.diff, ga, gb)
    return {"from": {"id": sa["id"], "version": sa["version"]}, "to": {"id": sb["id"], "version": sb["version"]}, **d}


# ------------------------------------------------------------------ baselines (desired state, curated + approved)
async def propose_baseline(ctx: RequestContext, snapshot_id: uuid.UUID, note: str) -> dict[str, Any]:
    async with uow(ctx) as conn:
        if not await resolve_snapshot(conn, ctx, snapshot_id):
            raise not_found("snapshot")
        bid = new_id()
        await conn.execute(baselines.insert().values(id=bid, org_id=ctx.org_id, project_id=ctx.project_id, snapshot_id=snapshot_id,
                                                     author_id=ctx.actor_id, note=note))
        await audit.record(conn, ctx, "architecture.baseline.propose", "architecture", bid, details={"snapshot_id": str(snapshot_id)})
        return row((await conn.execute(select(baselines).where(baselines.c.id == bid))).first())


async def get_baseline(ctx: RequestContext, bid: uuid.UUID) -> dict[str, Any]:
    async with uow(ctx) as conn:
        b = row((await conn.execute(select(baselines).where(baselines.c.id == bid))).first())
    if not b:
        raise not_found("baseline")
    return b




async def decide_baseline(ctx: RequestContext, bid: uuid.UUID, approve: bool, note: str = "", *, self_approval: bool = False) -> dict[str, Any]:
    """Four-eyes by default. `self_approval` (already authorized by Cerbos `self_approve_baseline`, org admins only) lets the
    author approve (reason optional); the exception is audited and stamped on the baseline note."""
    async with uow(ctx) as conn:
        b = row((await conn.execute(select(baselines).where(baselines.c.id == bid).with_for_update())).first())
        if not b or b["status"] != "proposed":
            raise problem(409, "AT-BASELINE-001", "Not pending", "Only proposed baselines can be decided.")
        own = b["author_id"] == ctx.actor_id
        if own and not (self_approval and approve):  # defense in depth; Cerbos already enforces author != approver
            raise problem(403, "AT-BASELINE-002", "Separation of duties", "The author cannot approve their own baseline.")
        if own:                                      # reasons are optional everywhere; the exception itself is still marked and audited
            note = f"[self-approved by organization admin] {note.strip()}".strip()
        now = datetime.now(UTC)
        if approve:
            await conn.execute(baselines.update().where(and_(baselines.c.project_id == ctx.project_id, baselines.c.status == "approved"))
                               .values(status="superseded"))
        await conn.execute(baselines.update().where(baselines.c.id == bid).values(
            status="approved" if approve else "rejected", approver_id=ctx.actor_id, decided_at=now,
            note=(b["note"] + ("\n" if b["note"] and note else "") + note)))
        action = "self_approve" if own else ("approve" if approve else "reject")
        await audit.record(conn, ctx, f"architecture.baseline.{action}", "architecture", bid,
                           details={"self_approved": own, "reason": note if own else ""})
        if approve:
            await outbox.emit(conn, ctx.org_id, ctx.project_id, "baseline", bid, "architecture.baseline_approved", {"baseline_id": str(bid)})
        return row((await conn.execute(select(baselines).where(baselines.c.id == bid))).first())


async def list_baselines(ctx: RequestContext) -> list[dict[str, Any]]:
    async with uow(ctx) as conn:
        return rows(await conn.execute(select(baselines, snapshots.c.version).join(snapshots, snapshots.c.id == baselines.c.snapshot_id)
                                       .where(baselines.c.project_id == ctx.project_id).order_by(baselines.c.proposed_at.desc())))


async def current_baseline(conn, ctx: RequestContext) -> dict[str, Any] | None:
    return row((await conn.execute(select(baselines).where(and_(baselines.c.project_id == ctx.project_id, baselines.c.status == "approved"))
                                   .order_by(baselines.c.decided_at.desc()).limit(1))).first())


# ------------------------------------------------------------------ curation
async def add_manual_element(ctx: RequestContext, subject_kind: str, key: str, kind: str, name: str, attributes: dict[str, Any],
                             retract: bool = False) -> dict[str, Any]:
    from archtwin.connectors.sdk import Observation
    attrs = {**attributes, **({"retracted": True} if retract else {})}
    o = Observation(origin="manual", subject_kind=subject_kind, subject_key=key, kind=kind, name=name, attributes=attrs,
                    parser_version="manual/1.0", source_ref=f"user:{ctx.actor_name}")
    oid = new_id()
    async with uow(ctx) as conn:
        await conn.execute(observations.insert().values(id=oid, org_id=ctx.org_id, project_id=ctx.project_id, origin="manual",
                                                        subject_kind=o.subject_kind, subject_key=o.subject_key, kind=o.kind, name=o.name,
                                                        attributes=o.attributes, source_ref=o.source_ref, parser_version=o.parser_version,
                                                        confidence=1, created_by=ctx.actor_id))
        await audit.record(conn, ctx, "architecture.manual_element", "architecture", key, details={"kind": kind, "retract": retract})
        await outbox.emit(conn, ctx.org_id, ctx.project_id, "inventory", ctx.project_id, "inventory.changed", {"manual": str(oid)})
    return {"observation_id": oid}


async def merge_identity(ctx: RequestContext, alias_key: str, canonical_key: str, reason: str) -> dict[str, Any]:
    if alias_key == canonical_key:
        raise problem(422, "AT-IDENTITY-001", "Cannot merge an element with itself")
    async with uow(ctx) as conn:
        await conn.execute(pg_insert(identity_aliases).values(id=new_id(), org_id=ctx.org_id, project_id=ctx.project_id, alias_key=alias_key,
                                                              canonical_key=canonical_key, reason=reason, created_by=ctx.actor_id)
                           .on_conflict_do_update(index_elements=["project_id", "alias_key"], set_={"canonical_key": canonical_key}))
        await conn.execute(identity_suggestions.update().where(and_(identity_suggestions.c.project_id == ctx.project_id,
                                                                    identity_suggestions.c.key_a.in_([alias_key, canonical_key]),
                                                                    identity_suggestions.c.key_b.in_([alias_key, canonical_key])))
                           .values(status="merged"))
        await audit.record(conn, ctx, "architecture.identity.merge", "architecture", canonical_key, details={"alias": alias_key, "reason": reason})
        await outbox.emit(conn, ctx.org_id, ctx.project_id, "inventory", ctx.project_id, "inventory.changed", {"merge": alias_key})
    return {"alias_key": alias_key, "canonical_key": canonical_key}


async def split_identity(ctx: RequestContext, alias_key: str) -> None:
    async with uow(ctx) as conn:
        await conn.execute(identity_aliases.delete().where(and_(identity_aliases.c.project_id == ctx.project_id,
                                                                identity_aliases.c.alias_key == alias_key)))
        await audit.record(conn, ctx, "architecture.identity.split", "architecture", alias_key)
        await outbox.emit(conn, ctx.org_id, ctx.project_id, "inventory", ctx.project_id, "inventory.changed", {"split": alias_key})


async def list_suggestions(ctx: RequestContext) -> list[dict[str, Any]]:
    async with uow(ctx) as conn:
        s = rows(await conn.execute(select(identity_suggestions).where(and_(identity_suggestions.c.project_id == ctx.project_id,
                                                                            identity_suggestions.c.status == "open"))))
        a = rows(await conn.execute(select(identity_aliases).where(identity_aliases.c.project_id == ctx.project_id)))
    return {"suggestions": s, "aliases": a}


async def snapshot_count(ctx: RequestContext) -> int:
    async with uow(ctx) as conn:
        return (await conn.execute(select(func.count()).select_from(snapshots).where(snapshots.c.project_id == ctx.project_id))).scalar()

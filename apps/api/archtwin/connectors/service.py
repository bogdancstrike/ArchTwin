"""Connector lifecycle: create (credentials sealed), test, request scan (outbox → Temporal), execute scan, persist evidence."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select

from archtwin.audit import service as audit
from archtwin.common import crypto
from archtwin.common.db import RequestContext, row, rows, uow
from archtwin.common.errors import not_found, problem
from archtwin.common.ids import new_id
from archtwin.common.logging import log, redact
from archtwin.common.schema import connectors, observations, scan_runs, secrets, source_artifacts
from archtwin.connectors import registry
from archtwin.connectors.sdk import ScanResult
from archtwin.documents import service as docs
from archtwin.flags import service as flags
from archtwin.kernel import outbox

PUBLIC_FIELDS = [c for c in connectors.c if c.name != "secret_id"]


async def require_enabled(ctx: RequestContext, kind: str) -> None:
    impl = registry.get(kind)
    if impl is None:
        raise problem(422, "AT-CONN-001", "Unknown connector kind", kind)
    await flags.require(ctx, "module.connector-platform", registry.MODULE_FLAG[kind], impl.flag)


async def _seal(conn, ctx: RequestContext, secret: dict[str, Any]) -> uuid.UUID:
    sid = new_id()
    env = crypto.seal(secret, aad=f"{ctx.org_id}/{ctx.project_id}/{sid}")
    await conn.execute(secrets.insert().values(id=sid, org_id=ctx.org_id, project_id=ctx.project_id, kek_id=env.kek_id,
                                               wrapped_dek=env.wrapped_dek, dek_nonce=env.dek_nonce, nonce=env.nonce,
                                               ciphertext=env.ciphertext))
    return sid


async def _unseal(conn, ctx: RequestContext, sid: uuid.UUID | None) -> dict[str, Any]:
    if not sid:
        return {}
    s = (await conn.execute(select(secrets).where(secrets.c.id == sid))).first()
    if not s:
        return {}
    return crypto.open_envelope(crypto.Envelope(s.kek_id, s.wrapped_dek, s.dek_nonce, s.nonce, s.ciphertext),
                                aad=f"{ctx.org_id}/{ctx.project_id}/{sid}")


def _public(c: dict[str, Any]) -> dict[str, Any]:
    c = dict(c)
    c["has_secret"] = bool(c.pop("secret_id", None))
    c["config"] = redact(c.get("config") or {})
    return c


async def create(ctx: RequestContext, kind: str, name: str, config: dict[str, Any], secret: dict[str, Any] | None,
                 freshness_sla_s: int | None) -> dict[str, Any]:
    await require_enabled(ctx, kind)
    impl = registry.get(kind)
    cid = new_id()
    async with uow(ctx) as conn:
        if (await conn.execute(select(connectors.c.id).where(and_(connectors.c.project_id == ctx.project_id, connectors.c.name == name)))).first():
            raise problem(409, "AT-CONN-002", "Name taken", f"A connector named {name!r} already exists in this project.")
        sid = await _seal(conn, ctx, secret) if secret else None
        await conn.execute(connectors.insert().values(id=cid, org_id=ctx.org_id, project_id=ctx.project_id, kind=kind, name=name,
                                                      config=config, secret_id=sid, created_by=ctx.actor_id,
                                                      freshness_sla_s=freshness_sla_s or impl.manifest["freshness_sla_s"]))
        await audit.record(conn, ctx, "connector.create", "connector", cid, details={"kind": kind, "name": name, "config": config})
        c = row((await conn.execute(select(*connectors.c).where(connectors.c.id == cid))).first())
    return _public(c)


async def list_(ctx: RequestContext) -> list[dict[str, Any]]:
    async with uow(ctx) as conn:
        cs = rows(await conn.execute(select(*connectors.c).where(connectors.c.project_id == ctx.project_id).order_by(connectors.c.created_at)))
    from archtwin.inventory.service import freshness
    return [{**_public(c), "freshness": freshness(c)} for c in cs]


async def get(ctx: RequestContext, cid: uuid.UUID) -> dict[str, Any]:
    async with uow(ctx) as conn:
        c = row((await conn.execute(select(*connectors.c).where(connectors.c.id == cid))).first())
    if not c:
        raise not_found("connector")
    return c


async def delete(ctx: RequestContext, cid: uuid.UUID) -> None:
    async with uow(ctx) as conn:
        c = row((await conn.execute(select(connectors).where(connectors.c.id == cid))).first())
        if not c:
            raise not_found("connector")
        # evidence is immutable and stays; the connector stops and its coverage lapses (absence => UNKNOWN, not deletion)
        await conn.execute(connectors.update().where(connectors.c.id == cid).values(enabled=False, name=c["name"] + f" (removed {cid.hex[:6]})"))
        if c["secret_id"]:
            await conn.execute(connectors.update().where(connectors.c.id == cid).values(secret_id=None))
            await conn.execute(secrets.delete().where(secrets.c.id == c["secret_id"]))
        await audit.record(conn, ctx, "connector.delete", "connector", cid)


async def test(ctx: RequestContext, cid: uuid.UUID) -> dict[str, Any]:
    c = await get(ctx, cid)
    await require_enabled(ctx, c["kind"])
    async with uow(ctx) as conn:
        sec = await _unseal(conn, ctx, c["secret_id"])
    res = await registry.get(c["kind"]).test(c["config"], sec)
    async with uow(ctx) as conn:
        await audit.record(conn, ctx, "connector.test", "connector", cid, details={"ok": res.ok})
    return {"ok": res.ok, "scopes": res.scopes, "warnings": res.warnings, "details": redact(res.details)}


async def request_scan(ctx: RequestContext, cid: uuid.UUID, ref: str | None) -> dict[str, Any]:
    c = await get(ctx, cid)
    if not c["enabled"]:
        raise problem(409, "AT-CONN-003", "Connector disabled")
    await require_enabled(ctx, c["kind"])
    sid = new_id()
    async with uow(ctx) as conn:
        await conn.execute(scan_runs.insert().values(id=sid, org_id=ctx.org_id, project_id=ctx.project_id, connector_id=cid,
                                                     ref=ref, requested_by=ctx.actor_id))
        await audit.record(conn, ctx, "connector.scan.request", "connector", cid, details={"scan_id": str(sid), "ref": ref})
        await outbox.emit(conn, ctx.org_id, ctx.project_id, "scan", sid, "connector.scan_requested",
                          {"scan_id": str(sid), "connector_id": str(cid)})
        return row((await conn.execute(select(scan_runs).where(scan_runs.c.id == sid))).first())


async def list_scans(ctx: RequestContext, cid: uuid.UUID | None = None, limit: int = 50) -> list[dict[str, Any]]:
    async with uow(ctx) as conn:
        q = select(scan_runs).where(scan_runs.c.project_id == ctx.project_id)
        if cid:
            q = q.where(scan_runs.c.connector_id == cid)
        return rows(await conn.execute(q.order_by(scan_runs.c.created_at.desc()).limit(limit)))


async def execute_scan(ctx: RequestContext, scan_id: uuid.UUID) -> dict[str, Any]:
    """Run inside a Temporal activity. Re-checks flags (a flag turned OFF after queueing stops the job safely)."""
    async with uow(ctx) as conn:
        s = row((await conn.execute(select(scan_runs).where(scan_runs.c.id == scan_id))).first())
        if not s or s["status"] not in ("queued", "running"):
            return {"status": s["status"] if s else "missing", "skipped": True}
        c = row((await conn.execute(select(connectors).where(connectors.c.id == s["connector_id"]))).first())
    impl = registry.get(c["kind"])
    for k in ("module.connector-platform", registry.MODULE_FLAG[c["kind"]], impl.flag):
        if not await flags.enabled(k, ctx.org_id, ctx.project_id):
            async with uow(ctx) as conn:
                await conn.execute(scan_runs.update().where(scan_runs.c.id == scan_id).values(
                    status="skipped", finished_at=datetime.now(UTC), error=f"flag {k} is off"))
            return {"status": "skipped", "reason": f"flag {k} off"}
    async with uow(ctx) as conn:
        await conn.execute(scan_runs.update().where(scan_runs.c.id == scan_id).values(status="running", started_at=datetime.now(UTC)))
        sec = await _unseal(conn, ctx, c["secret_id"])
    try:
        result: ScanResult = await impl.scan(c["config"], sec, s["ref"])
    except Exception as e:  # noqa: BLE001
        msg = redact(str(getattr(e, "problem_detail", None) or e))[:500]
        log.warning("scan_failed", scan_id=str(scan_id), error=msg)
        async with uow(ctx) as conn:
            await conn.execute(scan_runs.update().where(scan_runs.c.id == scan_id).values(status="failed", finished_at=datetime.now(UTC), error=msg))
            await conn.execute(connectors.update().where(connectors.c.id == c["id"]).values(last_status="failed", last_scan_id=scan_id))
            await audit.record(conn, ctx, "connector.scan.fail", "connector", c["id"], details={"scan_id": str(scan_id), "error": msg})
        return {"status": "failed", "error": msg}
    return await persist(ctx, c, scan_id, result)


async def persist(ctx: RequestContext, c: dict[str, Any], scan_id: uuid.UUID, result: ScanResult) -> dict[str, Any]:
    status = "complete" if result.complete else "partial"
    now = datetime.now(UTC)
    new_docs = 0
    async with uow(ctx) as conn:
        batch = [{"id": new_id(), "org_id": ctx.org_id, "project_id": ctx.project_id, "connector_id": c["id"], "scan_id": scan_id,
                  "origin": o.origin, "subject_kind": o.subject_kind, "subject_key": o.subject_key, "kind": o.kind, "name": o.name,
                  "attributes": o.attributes, "source_ref": o.source_ref, "source_revision": o.source_revision or result.revision,
                  "evidence": o.evidence, "observed_at": now, "parser_version": o.parser_version, "confidence": o.confidence,
                  "sensitive": o.sensitive} for o in result.observations]
        for i in range(0, len(batch), 500):
            await conn.execute(observations.insert(), batch[i:i + 500])
        for d in result.documents:
            _, created = await docs.upsert_document(conn, ctx, title=d.title, path=d.path, text_body=d.text, mime=d.mime,
                                                    source_kind="connector", connector_id=c["id"], revision=result.revision, tags=d.tags)
            new_docs += int(created)
        await conn.execute(source_artifacts.insert().values(
            id=new_id(), org_id=ctx.org_id, project_id=ctx.project_id, connector_id=c["id"], scan_id=scan_id,
            uri=f"{c['kind']}://{c['name']}@{result.revision or 'live'}", sha256=__import__("hashlib").sha256(
                "".join(sorted(o.subject_key for o in result.observations)).encode()).hexdigest(),
            kind=c["kind"], revision=result.revision, size=len(result.observations), parser_version=registry.get(c["kind"]).manifest["name"]))
        stats = {**result.stats, "observations": len(batch), "documents_new": new_docs, "warnings": result.warnings[:20]}
        await conn.execute(scan_runs.update().where(scan_runs.c.id == scan_id).values(
            status=status, finished_at=now, revision=result.revision, stats=stats, coverage=result.coverage))
        upd = {"last_status": status, "last_scan_id": scan_id, "last_success_at": now}
        if result.complete:
            upd["last_complete_at"] = now
        await conn.execute(connectors.update().where(connectors.c.id == c["id"]).values(**upd))
        await audit.record(conn, ctx, "connector.scan.complete", "connector", c["id"], details={"scan_id": str(scan_id), "status": status,
                                                                                              "observations": len(batch)})
        await outbox.emit(conn, ctx.org_id, ctx.project_id, "inventory", ctx.project_id, "inventory.changed",
                          {"scan_id": str(scan_id), "connector_id": str(c["id"])})
    return {"status": status, "observations": len(batch), "revision": result.revision, "documents_new": new_docs}

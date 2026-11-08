"""Tamper-evident audit log (AT-AUDIT_PROVENANCE-001..003, design D9).

hash = sha256(prev_hash || canonical_json(event)) per organization chain. Written in the SAME transaction as the action
(allow decisions) or in its own transaction (deny decisions). UPDATE/DELETE are revoked from the app role and blocked by
a trigger. `verify_chain()` recomputes the chain and reports gaps and tampering.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from archtwin.common.db import RequestContext, rows, uow
from archtwin.common.ids import new_id
from archtwin.common.logging import redact
from archtwin.common.schema import audit_events

GENESIS = "0" * 64


def canonical(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)


def chain_hash(prev: str, event: dict[str, Any]) -> str:
    return hashlib.sha256((prev + canonical(event)).encode()).hexdigest()


def _hashable(e: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "org_id", "seq", "occurred_at", "actor_id", "actor_name", "action", "resource_kind", "resource_id",
            "project_id", "decision", "trace_id", "details")
    out = {k: e.get(k) for k in keys}
    for k in ("id", "org_id", "actor_id", "project_id"):
        out[k] = str(out[k]) if out[k] else None
    if isinstance(out["occurred_at"], datetime):
        out["occurred_at"] = out["occurred_at"].astimezone(UTC).isoformat()
    return out


async def record(conn: AsyncConnection, ctx: RequestContext, action: str, resource_kind: str, resource_id: Any = "",
                 *, decision: str = "allow", details: dict[str, Any] | None = None,
                 project_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Append an audit event inside the caller's transaction (tenant already set on conn)."""
    head = (await conn.execute(text("SELECT seq, hash FROM audit_chain_heads WHERE org_id = :o FOR UPDATE"),
                               {"o": ctx.org_id})).first()
    if head is None:
        await conn.execute(text("INSERT INTO audit_chain_heads (org_id, seq, hash) VALUES (:o, 0, :h) ON CONFLICT DO NOTHING"),
                           {"o": ctx.org_id, "h": GENESIS})
        head = (await conn.execute(text("SELECT seq, hash FROM audit_chain_heads WHERE org_id = :o FOR UPDATE"),
                                   {"o": ctx.org_id})).first()
    seq, prev = head.seq + 1, head.hash
    ev = {"id": new_id(), "org_id": ctx.org_id, "seq": seq, "occurred_at": datetime.now(UTC).replace(microsecond=0),
          "actor_id": ctx.actor_id, "actor_name": ctx.actor_name, "action": action, "resource_kind": resource_kind,
          "resource_id": str(resource_id or ""), "project_id": project_id or ctx.project_id, "decision": decision,
          "trace_id": ctx.trace_id, "details": redact(details or {})}
    h = chain_hash(prev, _hashable(ev))
    await conn.execute(audit_events.insert().values(**ev, prev_hash=prev, hash=h))
    await conn.execute(text("UPDATE audit_chain_heads SET seq = :s, hash = :h WHERE org_id = :o"), {"s": seq, "h": h, "o": ctx.org_id})
    return {**ev, "hash": h, "prev_hash": prev}


async def record_denial(ctx: RequestContext, action: str, resource_kind: str, resource_id: Any = "", details: dict | None = None):
    """Deny decisions are audited in their own transaction (the denied action never committed anything)."""
    async with uow(RequestContext(ctx.principal, ctx.org_id, None, ctx.trace_id)) as conn:
        await record(conn, ctx, action, resource_kind, resource_id, decision="deny", details=details, project_id=ctx.project_id)


def verify_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure verification over an ordered event list (used by the API, the CLI and tests)."""
    prev, expected_seq, problems = GENESIS, 1, []
    for e in events:
        if e["seq"] != expected_seq:
            problems.append({"seq": e["seq"], "problem": f"gap: expected seq {expected_seq}"})
        if e["prev_hash"] != prev:
            problems.append({"seq": e["seq"], "problem": "prev_hash does not match previous event"})
        if chain_hash(e["prev_hash"], _hashable(e)) != e["hash"]:
            problems.append({"seq": e["seq"], "problem": "content hash mismatch (tampered)"})
        prev, expected_seq = e["hash"], e["seq"] + 1
    return {"ok": not problems, "events": len(events), "head": prev, "problems": problems}


async def verify_chain(ctx: RequestContext) -> dict[str, Any]:
    async with uow(RequestContext(ctx.principal, ctx.org_id)) as conn:
        evs = rows(await conn.execute(select(audit_events).where(audit_events.c.org_id == ctx.org_id).order_by(audit_events.c.seq)))
    return verify_events(evs)

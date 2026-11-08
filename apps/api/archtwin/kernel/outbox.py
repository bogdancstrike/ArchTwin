"""Transactional outbox (AT-CANONICAL_EVENTS-001..003, design D7).

`emit()` inserts the event in the caller's transaction, so a rolled-back command emits nothing. The relay (worker) claims
rows with FOR UPDATE SKIP LOCKED, is woken by NOTIFY, retries with exponential backoff and dead-letters after N attempts.
Consumers record (consumer, event_id) receipts so redelivery after a crash is applied once.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from archtwin.common.ids import new_id
from archtwin.common.schema import consumer_receipts, outbox_events

CHANNEL = "archtwin_outbox"
MAX_ATTEMPTS = 8


async def emit(conn: AsyncConnection, org_id: uuid.UUID, project_id: uuid.UUID | None, aggregate_kind: str,
               aggregate_id: Any, event_kind: str, payload: dict[str, Any]) -> uuid.UUID:
    eid = new_id()
    # event payloads carry IDs only, never tenant content (no cross-project leakage through events)
    await conn.execute(outbox_events.insert().values(id=eid, org_id=org_id, project_id=project_id, aggregate_kind=aggregate_kind,
                                                     aggregate_id=str(aggregate_id), event_kind=event_kind, payload=payload))
    await conn.execute(text(f"NOTIFY {CHANNEL}"))
    return eid


async def claim(conn: AsyncConnection, limit: int = 20) -> list[dict[str, Any]]:
    rs = await conn.execute(text("""
        SELECT * FROM outbox_events WHERE status = 'pending' AND next_attempt_at <= now()
        ORDER BY occurred_at FOR UPDATE SKIP LOCKED LIMIT :n"""), {"n": limit})
    return [dict(r._mapping) for r in rs]


async def mark_delivered(conn: AsyncConnection, eid: uuid.UUID) -> None:
    await conn.execute(text("UPDATE outbox_events SET status='delivered', delivered_at=now(), attempts=attempts+1 WHERE id=:i"),
                       {"i": eid})


async def mark_failed(conn: AsyncConnection, ev: dict[str, Any], error: str) -> None:
    attempts = ev["attempts"] + 1
    status = "dead" if attempts >= MAX_ATTEMPTS else "pending"
    nxt = datetime.now(UTC) + timedelta(seconds=min(300, 2 ** attempts))
    await conn.execute(text("UPDATE outbox_events SET status=:s, attempts=:a, next_attempt_at=:n, last_error=:e WHERE id=:i"),
                       {"s": status, "a": attempts, "n": nxt, "e": error[:500], "i": ev["id"]})


async def first_time(conn: AsyncConnection, consumer: str, event_id: uuid.UUID) -> bool:
    """Idempotent consumer receipt: True only the first time (consumer, event) is seen."""
    r = await conn.execute(pg_insert(consumer_receipts).values(consumer=consumer, event_id=event_id).on_conflict_do_nothing())
    return r.rowcount == 1

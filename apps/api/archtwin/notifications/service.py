"""In-app notifications (AT-ARCHITECTURE_NOTIFICATIONS-001): per-recipient rows, dedupe with occurrence count, SSE feed.

Recipients are re-derived from current project membership at send time (authorization re-check)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from archtwin.common.db import RequestContext, rows, uow
from archtwin.common.ids import new_id
from archtwin.common.schema import notifications, project_members


async def notify_project(conn, ctx: RequestContext, *, kind: str, title: str, body: str, link: str, dedupe_key: str) -> int:
    members = (await conn.execute(select(project_members.c.user_id).where(project_members.c.project_id == ctx.project_id))).all()
    for m in members:
        await conn.execute(pg_insert(notifications).values(
            id=new_id(), org_id=ctx.org_id, project_id=ctx.project_id, user_id=m.user_id, kind=kind, title=title[:300], body=body[:1000],
            link=link, dedupe_key=dedupe_key).on_conflict_do_update(
            index_elements=["user_id", "dedupe_key"],
            set_={"occurrences": notifications.c.occurrences + 1, "read_at": None, "title": title[:300], "created_at": func.now()}))
    await conn.execute(text("NOTIFY archtwin_notifications"))
    return len(members)


async def list_for(ctx: RequestContext, unread_only: bool = False, limit: int = 50) -> list[dict[str, Any]]:
    async with uow(RequestContext(ctx.principal, ctx.org_id)) as conn:
        q = select(notifications).where(notifications.c.user_id == ctx.actor_id)
        if unread_only:
            q = q.where(notifications.c.read_at.is_(None))
        return rows(await conn.execute(q.order_by(notifications.c.created_at.desc()).limit(limit)))


async def mark_read(ctx: RequestContext, ids: list[uuid.UUID] | None) -> None:
    async with uow(RequestContext(ctx.principal, ctx.org_id)) as conn:
        q = notifications.update().where(and_(notifications.c.user_id == ctx.actor_id, notifications.c.read_at.is_(None)))
        if ids:
            q = q.where(notifications.c.id.in_(ids))
        await conn.execute(q.values(read_at=func.now()))

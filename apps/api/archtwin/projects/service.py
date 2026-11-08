"""Organizations' projects, environments and memberships (AT-ORGANIZATIONS, AT-PROJECT_BOUNDARIES)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, select

from archtwin.audit import service as audit
from archtwin.common import authz
from archtwin.common.db import RequestContext, row, rows, uow
from archtwin.common.errors import not_found, problem
from archtwin.common.ids import new_id
from archtwin.common.schema import environments, project_members, projects, users
from archtwin.iam.service import slugify
from archtwin.kernel import outbox


async def list_projects(ctx: RequestContext) -> list[dict[str, Any]]:
    where = await authz.plan_filter(ctx.principal, "project", "view", projects,
                                    {"request.resource.attr.project_id": projects.c.id, "request.resource.attr.org_id": projects.c.org_id})
    async with uow(ctx) as conn:
        rs = rows(await conn.execute(select(projects).where(where).order_by(projects.c.created_at)))
    for r in rs:
        r["my_role"] = ctx.principal.project_roles.get(str(r["id"])) or ("org_admin" if ctx.principal.is_org_admin else None)
    return rs


async def create_project(ctx: RequestContext, title: str, purpose: str, tags: list[str], envs: list[str]) -> dict[str, Any]:
    pid = new_id()
    base = slugify(title)
    async with uow(ctx) as conn:
        slug, n = base, 1
        while (await conn.execute(select(projects.c.id).where(projects.c.slug == slug))).first():
            n += 1
            slug = f"{base}-{n}"
        # org_id comes from the verified context only; any org_id in the client payload is ignored
        await conn.execute(projects.insert().values(id=pid, org_id=ctx.org_id, slug=slug, title=title, purpose=purpose,
                                                    tags=tags, created_by=ctx.actor_id))
        pctx = ctx.for_project(pid)
        for e in envs or ["production"]:
            await conn.execute(environments.insert().values(id=new_id(), org_id=ctx.org_id, project_id=pid, name=e))
        await conn.execute(project_members.insert().values(org_id=ctx.org_id, project_id=pid, user_id=ctx.actor_id, role="project_owner"))
        await audit.record(conn, pctx, "project.create", "project", pid, details={"title": title, "slug": slug})
        await outbox.emit(conn, ctx.org_id, pid, "project", pid, "project.created", {"project_id": str(pid)})
        return row((await conn.execute(select(projects).where(projects.c.id == pid))).first())


async def get_project(ctx: RequestContext) -> dict[str, Any]:
    async with uow(ctx) as conn:
        p = row((await conn.execute(select(projects).where(projects.c.id == ctx.project_id))).first())
        if not p:
            raise not_found("project")
        p["environments"] = rows(await conn.execute(select(environments).where(environments.c.project_id == ctx.project_id)
                                                    .order_by(environments.c.created_at)))
    p["my_role"] = ctx.principal.project_roles.get(str(ctx.project_id)) or ("org_admin" if ctx.principal.is_org_admin else None)
    return p


async def update_project(ctx: RequestContext, revision: int, changes: dict[str, Any]) -> dict[str, Any]:
    allowed = {k: v for k, v in changes.items() if k in ("title", "purpose", "tags", "status") and v is not None}
    async with uow(ctx) as conn:
        r = await conn.execute(projects.update().where(and_(projects.c.id == ctx.project_id, projects.c.revision == revision))
                               .values(**allowed, revision=projects.c.revision + 1, updated_at=func.now()))
        if r.rowcount == 0:
            raise problem(412, "AT-REVISION-001", "Revision mismatch", "The project changed since you loaded it (If-Match).")
        await audit.record(conn, ctx, "project.update", "project", ctx.project_id, details=allowed)
    return await get_project(ctx)


async def list_members(ctx: RequestContext) -> list[dict[str, Any]]:
    async with uow(ctx) as conn:
        return rows(await conn.execute(select(project_members.c.user_id, project_members.c.role, users.c.username, users.c.display_name)
                                       .join(users, users.c.id == project_members.c.user_id)
                                       .where(project_members.c.project_id == ctx.project_id).order_by(users.c.username)))


ROLES = {"project_owner", "architect", "tech_lead", "contributor", "reviewer", "viewer"}


async def set_member(ctx: RequestContext, user_id: uuid.UUID, role: str | None) -> list[dict[str, Any]]:
    if role is not None and role not in ROLES:
        raise problem(422, "AT-MEMBER-001", "Unknown role", role)
    async with uow(ctx) as conn:
        owners = [m.user_id for m in (await conn.execute(select(project_members.c.user_id).where(and_(
            project_members.c.project_id == ctx.project_id, project_members.c.role == "project_owner")))).all()]
        if user_id in owners and role != "project_owner" and len(owners) == 1:
            raise problem(409, "AT-MEMBER-002", "Last owner", "A project must keep at least one owner.")
        await conn.execute(project_members.delete().where(and_(project_members.c.project_id == ctx.project_id,
                                                               project_members.c.user_id == user_id)))
        if role:
            await conn.execute(project_members.insert().values(org_id=ctx.org_id, project_id=ctx.project_id, user_id=user_id, role=role))
        await audit.record(conn, ctx, "project.member.set", "project", ctx.project_id, details={"user_id": str(user_id), "role": role})
    return await list_members(ctx)

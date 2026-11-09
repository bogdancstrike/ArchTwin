"""FastAPI dependencies: authentication → principal → request context → project scope (Cerbos-checked)."""
from __future__ import annotations

import uuid

from fastapi import Depends, Header, Request
from sqlalchemy import select

from archtwin.audit import service as audit
from archtwin.common import authz
from archtwin.common.auth import verify
from archtwin.common.db import Principal, RequestContext, uow
from archtwin.common.errors import not_found, problem
from archtwin.common.schema import projects
from archtwin.iam.service import load_principal


async def principal(request: Request, x_archtwin_org: str | None = Header(default=None)) -> Principal:
    if (p := getattr(request.state, "principal", None)) is not None:
        return p
    h = request.headers.get("authorization", "")
    token = h[7:] if h.lower().startswith("bearer ") else request.query_params.get("access_token", "") \
        if request.url.path.endswith("/stream") else ""
    if not token:
        raise problem(401, "AT-AUTH-001", "Missing bearer token")
    ident = await verify(token)                       # 401 before any DB access
    p = await load_principal(ident, x_archtwin_org)
    request.state.principal = p
    return p


async def ctx(request: Request, p: Principal = Depends(principal)) -> RequestContext:
    return RequestContext(p, p.org_id, None, request.headers.get("x-request-id", "") or getattr(request.state, "trace_id", ""))


async def project_ctx(project_id: uuid.UUID, c: RequestContext = Depends(ctx)) -> RequestContext:
    async with uow(c) as conn:
        pr = (await conn.execute(select(projects.c.id, projects.c.org_id).where(projects.c.id == project_id))).first()
    if pr is None:
        raise not_found("project")
    if not await authz.allowed(c.principal, "project", "view", str(project_id),
                               {"org_id": str(pr.org_id), "project_id": str(project_id)}):
        await audit.record_denial(c.for_project(project_id), "project.view", "project", project_id)
        raise not_found("project")
    return c.for_project(project_id)


async def require(c: RequestContext, kind: str, action: str, rid: str = "", **attr) -> None:
    """Cerbos check for a project-scoped resource; deny is audited and returned as 403."""
    a = {"org_id": str(c.org_id), "project_id": str(c.project_id) if c.project_id else "", **attr}
    if not await authz.allowed(c.principal, kind, action, rid, a):
        await audit.record_denial(c, f"{kind}.{action}", kind, rid)
        raise problem(403, "AT-AUTHZ-001", "Forbidden", f"You may not {action} this {kind}.")


async def org_allowed(c: RequestContext, action: str) -> bool:
    """Cerbos check on the organization resource (admin pages, usage, spend limits)."""
    return await authz.allowed(c.principal, "org", action, str(c.org_id), {"org_id": str(c.org_id)})


async def org_require(c: RequestContext, action: str) -> None:
    """Org-level authorization; deny is audited and returned as 403."""
    if not await org_allowed(c, action):
        await audit.record_denial(c, f"org.{action}", "org", c.org_id)
        raise problem(403, "AT-AUTHZ-001", "Forbidden", f"You may not {action.replace('_', ' ')}.")

"""Audit page search (filters, categories, sort, pagination, summaries)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from archtwin.api.deps import ctx as get_ctx
from archtwin.audit import search as audit_search
from archtwin.audit import service as audit
from archtwin.common import authz
from archtwin.common.db import RequestContext
from archtwin.common.errors import problem

router = APIRouter(prefix="/api/v1", tags=["audit"])


@router.get("/audit/search")
async def search(page: int = Query(1, ge=1), page_size: int = Query(25), sort: str = "when", dir: str = Query("desc", pattern="^(asc|desc)$"),
                 q: str | None = Query(None, max_length=200), actor: str | None = None, result: str | None = Query(None, pattern="^(allow|deny)$"),
                 category: str | None = None, since: datetime | None = None, until: datetime | None = None,
                 project_id: uuid.UUID | None = None, c: RequestContext = Depends(get_ctx)):
    if not await authz.allowed(c.principal, "audit", "view", "", {"org_id": str(c.org_id), "project_id": ""}):
        await audit.record_denial(c, "audit.view", "audit")
        raise problem(403, "AT-AUTHZ-001", "Forbidden")
    return await audit_search.search(c, audit_search.AuditQuery(page, page_size, sort, dir, q, actor, result, category, since, until, project_id))

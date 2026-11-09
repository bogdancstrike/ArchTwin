"""Architecture exploration beyond C4 views: recognized flows, element search and element detail."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from archtwin.api.deps import project_ctx, require
from archtwin.architecture import explore, flows
from archtwin.architecture import service as arch
from archtwin.common.db import RequestContext
from archtwin.flags import service as flags

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["architecture"])


async def _view(c: RequestContext) -> None:
    await flags.require(c, "module.architecture-graph")
    await require(c, "architecture", "view")


@router.get("/flows")
async def project_flows(snapshot_id: uuid.UUID | None = None, c: RequestContext = Depends(project_ctx)):
    """Automatically recognized request, event and data flows (deterministic, from every datasource's evidence)."""
    await _view(c)
    g = await arch.graph(c, snapshot_id)
    return {"snapshot_id": str(g["snapshot"]["id"]) if g.get("snapshot") else None, **flows.recognize(g)}


@router.get("/elements/search")
async def element_search(q: str = Query(..., min_length=1, max_length=120), limit: int = Query(30, le=100), c: RequestContext = Depends(project_ctx)):
    await _view(c)
    return explore.search(await arch.graph(c), q, limit)


@router.get("/elements/detail")
async def element_detail(key: str = Query(..., min_length=3, max_length=600), c: RequestContext = Depends(project_ctx)):
    await _view(c)
    return await explore.detail(c, await arch.graph(c), key)

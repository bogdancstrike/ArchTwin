"""Exports: GET /projects/{pid}/export/{resource}?format=md|docx|pdf|zip[&id=…] — same flags and view permission as the page."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse

from archtwin import exports
from archtwin.api.deps import project_ctx, require
from archtwin.audit import service as audit
from archtwin.common.db import RequestContext, uow
from archtwin.common.errors import problem
from archtwin.flags import service as flags

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["exports"])

# resource -> (feature flag of the page, Cerbos resource kind, action)
GUARDS = {
    "architecture": ("module.architecture-graph", "architecture", "view"),
    "flows": ("module.architecture-graph", "architecture", "view"),
    "drift": ("module.drift-engine", "drift_finding", "view"),
    "decisions": ("module.adr-workflow", "adr", "view"),
    "docs": ("module.documentation-engine", "document", "export"),
}


@router.get("/export/{resource}")
async def export(resource: str, format: str = Query("md", pattern="^(md|docx|pdf|zip)$"), id: str | None = Query(None, max_length=200),
                 status: str | None = None, verdict: str | None = None, severity: str | None = None,
                 c: RequestContext = Depends(project_ctx)):
    if resource not in GUARDS:
        raise problem(422, "AT-EXPORT-001", "Unknown export", f"resource must be one of {', '.join(GUARDS)}")
    flag, kind, action = GUARDS[resource]
    await flags.require(c, flag)
    await require(c, kind, action)
    col = await exports.collect(c, resource, id, {"status": status, "verdict": verdict, "severity": severity})
    art = exports.render(col, format)
    async with uow(c) as conn:
        await audit.record(conn, c, f"export.{resource}", resource, id or "", details={"format": format, "items": len(col.items)})
    headers = {"Content-Disposition": f'attachment; filename="{art.filename}"', "Cache-Control": "no-store"}
    if art.stream is not None:
        return StreamingResponse(art.stream, media_type=art.media_type, headers=headers)
    return Response(art.body, media_type=art.media_type, headers=headers)

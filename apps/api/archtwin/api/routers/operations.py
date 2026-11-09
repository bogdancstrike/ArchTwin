"""Operations: AI usage & cost, spend limits, system health, local source roots, roles & permissions (org admin pages)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, Response

from archtwin.api import schemas as S
from archtwin.api.deps import ctx as get_ctx
from archtwin.api.deps import org_allowed, org_require
from archtwin.common import authz
from archtwin.common.db import RequestContext
from archtwin.common.errors import problem
from archtwin.connectors.adapters import git_repo
from archtwin.intelligence import usage
from archtwin.operations import service as ops

router = APIRouter(prefix="/api/v1", tags=["operations"])
SCOPE = Query("me", pattern="^(me|all)$")
DAYS = Query(30, ge=1, le=400)


async def _everyone(c: RequestContext, scope: str) -> bool:
    """`me`: your own calls (view_own_usage); `all`: the whole organization (view_usage_all)."""
    await org_require(c, "view_own_usage")
    if scope == "all":
        await org_require(c, "view_usage_all")
        return True
    return False


@router.get("/usage/overview")
async def usage_overview(days: int = DAYS, scope: str = SCOPE, c: RequestContext = Depends(get_ctx)):
    return await ops.overview(c, days, await _everyone(c, scope))


@router.get("/usage/breakdown")
async def usage_breakdown(days: int = DAYS, group_by: str = "model", granularity: str = "day", scope: str = SCOPE,
                          c: RequestContext = Depends(get_ctx)):
    return await ops.breakdown(c, days, group_by, granularity, await _everyone(c, scope))


@router.get("/usage/export")
async def usage_export(days: int = DAYS, scope: str = SCOPE, c: RequestContext = Depends(get_ctx)):
    body = await ops.export_csv(c, days, await _everyone(c, scope))
    return Response(body, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="archtwin-ai-usage-{days}d.csv"'})


@router.get("/admin/spend-limits")
async def get_spend_limits(c: RequestContext = Depends(get_ctx)):
    await org_require(c, "manage_spend_limits")
    return {"items": await ops.labeled_limits(c), "warn_at": usage.WARN_AT, "prices": usage.price_table()}


@router.put("/admin/spend-limits")
async def put_spend_limits(body: S.SpendLimitsIn, c: RequestContext = Depends(get_ctx)):
    await org_require(c, "manage_spend_limits")
    return {"items": await ops.set_limits(c, [i.model_dump() for i in body.items])}


@router.get("/admin/system")
async def admin_system(c: RequestContext = Depends(get_ctx)):
    await org_require(c, "view_system")
    return await ops.system(c)


@router.get("/admin/source-roots")
async def admin_source_roots(c: RequestContext = Depends(get_ctx)):
    await org_require(c, "view_system")
    return await ops.source_roots(c)


@router.put("/admin/source-roots")
async def admin_set_source_roots(body: S.SourceRootsIn, c: RequestContext = Depends(get_ctx)):
    await org_require(c, "manage")
    return await ops.set_source_roots(c, body.roots)


@router.get("/admin/source-folders")
async def admin_source_folders(path: str | None = None, c: RequestContext = Depends(get_ctx)):
    """Folder picker over the mounted boundaries (not only the whitelist) to choose roots to whitelist; names only."""
    await org_require(c, "manage")
    git_repo.ORG_ROOTS.set(None)
    try:
        return await asyncio.to_thread(git_repo.browse, path)
    except ValueError as e:
        raise problem(422, "AT-CONN-004", "Folder not available", str(e)) from e


@router.get("/admin/access")
async def admin_access(c: RequestContext = Depends(get_ctx)):
    await org_require(c, "inspect_access")
    return await ops.access_matrix(c)


@router.get("/admin/policies")
async def admin_policies(c: RequestContext = Depends(get_ctx)):
    await org_require(c, "inspect_access")
    return {**ops.policy_files(), "pdp_healthy": await authz.healthy()}


@router.get("/me/permissions", tags=["identity"])
async def my_org_permissions(c: RequestContext = Depends(get_ctx)):
    """Which org-level pages the UI should show (Cerbos would deny the rest anyway)."""
    actions = ("view_own_usage", "view_usage_all", "manage_spend_limits", "view_system", "inspect_access", "view_audit", "manage")
    return {a: await org_allowed(c, a) for a in actions}

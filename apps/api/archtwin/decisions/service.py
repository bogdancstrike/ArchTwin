"""Architecture decision records, MADR format (AT-ADR_WORKFLOW-001..002).

States: proposed → accepted | rejected; accepted → superseded (by a newer ADR). Accepted versions are immutable
(adr_versions is append-only); editing an accepted ADR is refused — supersede it instead.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, select

from archtwin.audit import service as audit
from archtwin.common.db import RequestContext, row, rows, uow
from archtwin.common.errors import not_found, problem
from archtwin.common.ids import new_id
from archtwin.common.paging import PageQuery, paginate_select
from archtwin.common.schema import adr_versions, adrs, users

MADR_FIELDS = ("context", "decision_drivers", "considered_options", "decision_outcome", "consequences")


def _content(c: dict[str, Any]) -> dict[str, Any]:
    out = {k: c.get(k) for k in MADR_FIELDS}
    out["decision_drivers"] = [str(x) for x in (out["decision_drivers"] or [])][:20]
    out["considered_options"] = [{"name": str(o.get("name", ""))[:200], "pros": [str(p) for p in o.get("pros", [])][:10],
                                  "cons": [str(p) for p in o.get("cons", [])][:10]} if isinstance(o, dict) else {"name": str(o)[:200], "pros": [], "cons": []}
                                 for o in (out["considered_options"] or [])][:10]
    for k in ("context", "decision_outcome", "consequences"):
        out[k] = str(out[k] or "")[:20000]
    if c.get("citations"):
        out["citations"] = c["citations"]
    return out


async def create(ctx: RequestContext, title: str, content: dict[str, Any], links: list[str], ai_drafted: bool = False) -> dict[str, Any]:
    aid = new_id()
    async with uow(ctx) as conn:
        num = ((await conn.execute(select(func.max(adrs.c.number)).where(adrs.c.project_id == ctx.project_id))).scalar() or 0) + 1
        await conn.execute(adrs.insert().values(id=aid, org_id=ctx.org_id, project_id=ctx.project_id, number=num, title=title[:300],
                                                author_id=ctx.actor_id, ai_drafted=ai_drafted))
        await conn.execute(adr_versions.insert().values(adr_id=aid, version=1, org_id=ctx.org_id, project_id=ctx.project_id,
                                                        content=_content(content), links=links[:100], created_by=ctx.actor_id))
        await audit.record(conn, ctx, "adr.create", "adr", aid, details={"number": num, "title": title, "ai_drafted": ai_drafted})
    return await get(ctx, aid)


async def get(ctx: RequestContext, aid: uuid.UUID) -> dict[str, Any]:
    async with uow(ctx) as conn:
        a = row((await conn.execute(select(adrs).where(adrs.c.id == aid))).first())
        if not a:
            raise not_found("ADR")
        a["versions"] = rows(await conn.execute(select(adr_versions).where(adr_versions.c.adr_id == aid).order_by(adr_versions.c.version)))
        a["current"] = a["versions"][-1]
        names = {u.id: u.username for u in (await conn.execute(select(users.c.id, users.c.username)
                                                                .where(users.c.id.in_([x for x in (a["author_id"], a["approver_id"]) if x])))).all()}
    a["author"], a["approver"] = names.get(a["author_id"]), names.get(a["approver_id"])
    return a


ADR_SORTS = {"number": adrs.c.number, "title": adrs.c.title, "status": adrs.c.status, "created_at": adrs.c.created_at}


async def list_(ctx: RequestContext) -> list[dict[str, Any]]:
    async with uow(ctx) as conn:
        return rows(await conn.execute(select(adrs).where(adrs.c.project_id == ctx.project_id).order_by(adrs.c.number.desc())))


async def page(ctx: RequestContext, pq: PageQuery, status: str | None = None) -> dict[str, Any]:
    q = select(adrs).where(adrs.c.project_id == ctx.project_id)
    if status:
        q = q.where(adrs.c.status == status)
    async with uow(ctx) as conn:
        return await paginate_select(conn, q, pq, search=[adrs.c.title], sorts=ADR_SORTS, default_sort="number")


async def edit(ctx: RequestContext, aid: uuid.UUID, title: str | None, content: dict[str, Any], links: list[str]) -> dict[str, Any]:
    async with uow(ctx) as conn:
        a = row((await conn.execute(select(adrs).where(adrs.c.id == aid).with_for_update())).first())
        if not a:
            raise not_found("ADR")
        if a["status"] != "proposed":
            raise problem(409, "AT-ADR-001", "Immutable", "Accepted, rejected or superseded ADRs cannot be edited; supersede instead.")
        v = a["current_version"] + 1
        await conn.execute(adr_versions.insert().values(adr_id=aid, version=v, org_id=ctx.org_id, project_id=ctx.project_id,
                                                        content=_content(content), links=links[:100], created_by=ctx.actor_id))
        await conn.execute(adrs.update().where(adrs.c.id == aid).values(current_version=v, **({"title": title[:300]} if title else {})))
        await audit.record(conn, ctx, "adr.edit", "adr", aid, details={"version": v})
    return await get(ctx, aid)


async def decide(ctx: RequestContext, aid: uuid.UUID, accept: bool, supersedes: uuid.UUID | None = None) -> dict[str, Any]:
    async with uow(ctx) as conn:
        a = row((await conn.execute(select(adrs).where(adrs.c.id == aid).with_for_update())).first())
        if not a:
            raise not_found("ADR")
        if a["status"] != "proposed":
            raise problem(409, "AT-ADR-002", "Not proposed", "Only proposed ADRs can be accepted or rejected.")
        if a["author_id"] == ctx.actor_id:
            raise problem(403, "AT-ADR-003", "Separation of duties", "The author cannot approve their own ADR.")
        now = datetime.now(UTC)
        await conn.execute(adrs.update().where(adrs.c.id == aid).values(status="accepted" if accept else "rejected",
                                                                        approver_id=ctx.actor_id, decided_at=now,
                                                                        supersedes_id=supersedes if accept else None))
        if accept and supersedes:
            await conn.execute(adrs.update().where(and_(adrs.c.id == supersedes, adrs.c.status == "accepted"))
                               .values(status="superseded", superseded_by_id=aid))
        await audit.record(conn, ctx, f"adr.{'accept' if accept else 'reject'}", "adr", aid, details={"supersedes": str(supersedes) if supersedes else None})
    return await get(ctx, aid)


def to_markdown(a: dict[str, Any]) -> str:
    c = a["current"]["content"]
    lines = [f"# {a['number']:04d}. {a['title']}", "", f"* Status: {a['status']}", f"* Deciders: {a.get('author') or ''}"
             + (f", {a['approver']}" if a.get("approver") else ""), f"* Date: {(a.get('decided_at') or a['created_at']):%Y-%m-%d}", "",
             "## Context and Problem Statement", "", c.get("context") or "", "", "## Decision Drivers", ""]
    lines += [f"* {d}" for d in c.get("decision_drivers") or []] + ["", "## Considered Options", ""]
    lines += [f"* {o['name']}" for o in c.get("considered_options") or []]
    lines += ["", "## Decision Outcome", "", c.get("decision_outcome") or "", "", "### Consequences", "", c.get("consequences") or "", ""]
    for o in c.get("considered_options") or []:
        lines += [f"### {o['name']}", ""] + [f"* Good, because {p}" for p in o.get("pros", [])] + [f"* Bad, because {p}" for p in o.get("cons", [])] + [""]
    if a["current"].get("links"):
        lines += ["## Affected elements", ""] + [f"* `{k}`" for k in a["current"]["links"]] + [""]
    return "\n".join(lines)

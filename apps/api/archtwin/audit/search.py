"""Audit search for the Audit page: filters, categories, sorting, pagination and a one-sentence summary per event.

Read-only over the append-only, hash-chained `audit_events` (org RLS). Summaries are deterministic (verb table) so the
page never depends on an LLM to explain what happened.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select, text

from archtwin.common.db import RequestContext, rows, unscoped, uow
from archtwin.common.errors import problem
from archtwin.common.schema import audit_events, projects

PAGE_SIZES = (10, 25, 50, 100)
CATEGORIES: dict[str, tuple[str, ...]] = {          # category chip -> action prefixes
    "datasources": ("connector.", "document.", "source_roots."),
    "architecture": ("architecture.", "baseline.", "diagram.", "drift.", "suppression."),
    "decisions": ("adr.",),
    "ai": ("ai.", "usage.", "spend_limits."),
    "access": ("project.member", "member.", "access.", "flag.", "org."),
    "exports": ("export", "usage.export", "audit.export", "diagram.export"),
}
SORTS = {"when": audit_events.c.seq, "who": audit_events.c.actor_name, "what": audit_events.c.action, "result": audit_events.c.decision}
VERBS: list[tuple[str, str]] = [
    ("connector.create", "added datasource"), ("connector.delete", "removed datasource"), ("connector.test", "tested datasource"),
    ("connector.scan.request", "requested a scan of"), ("connector.scan.complete", "finished scanning"), ("connector.scan.fail", "failed scanning"),
    ("connector.webhook", "received a webhook for"), ("ai.general", "asked a general AI question"), ("ai.ask", "asked the assistant about"),
    ("ai.design", "requested an integration design in"), ("ai.text_extend", "extended text with AI in"),
    ("ai.architecture_draft", "drafted architecture with AI in"), ("ai.conversation.archive", "deleted a conversation"),
    ("adr.", "changed decision record"), ("baseline.", "changed a baseline in"), ("flag.update", "changed feature flag"),
    ("spend_limits.update", "changed AI spend limits"), ("source_roots.update", "changed local source roots"),
    ("usage.export", "exported AI usage"), ("access.inspect", "inspected roles & permissions"), ("project.create", "created project"),
    ("project.delete", "deleted project"),
]


@dataclass(frozen=True)
class AuditQuery:
    page: int = 1
    page_size: int = 25
    sort: str = "when"
    direction: str = "desc"
    q: str | None = None
    actor: str | None = None
    result: str | None = None              # allow | deny
    category: str | None = None
    since: datetime | None = None
    until: datetime | None = None          # a date (00:00) is inclusive of that whole day
    project_id: uuid.UUID | None = None

    def validate(self) -> None:
        if self.page_size not in PAGE_SIZES:
            raise problem(422, "AT-AUDIT-002", "Invalid page size", ", ".join(map(str, PAGE_SIZES)))
        if self.category and self.category not in CATEGORIES:
            raise problem(422, "AT-AUDIT-003", "Unknown category", ", ".join(CATEGORIES))


def summarize(e: dict[str, Any], project_titles: dict[str, str]) -> str:
    verb = next((v for prefix, v in VERBS if e["action"].startswith(prefix)), e["action"].replace(".", " "))
    target = (e.get("details") or {}).get("name") or (e["resource_kind"] if e["resource_kind"] not in ("org", "assistant") else "")
    where = project_titles.get(str(e.get("project_id")), "")
    text_ = f"{e['actor_name']} {verb}" + (f" {target}" if target and target not in verb else "") + (f" · {where}" if where else "")
    return ("DENIED: " + text_) if e["decision"] != "allow" else text_


def _conditions(ctx: RequestContext, q: AuditQuery) -> list[Any]:
    cond: list[Any] = [audit_events.c.org_id == ctx.org_id]
    if q.project_id:
        cond.append(audit_events.c.project_id == q.project_id)
    if q.actor:
        cond.append(audit_events.c.actor_name == q.actor)
    if q.result:
        cond.append(audit_events.c.decision == "allow" if q.result == "allow" else audit_events.c.decision != "allow")
    if q.category:
        cond.append(or_(*[audit_events.c.action.like(f"{p}%") for p in CATEGORIES[q.category]]))
    if q.since:
        cond.append(audit_events.c.occurred_at >= q.since)
    if q.until:
        whole_day = q.until.hour == 0 and q.until.minute == 0 and q.until.second == 0
        cond.append(audit_events.c.occurred_at < q.until + timedelta(days=1) if whole_day else audit_events.c.occurred_at <= q.until)
    if q.q:
        like = f"%{q.q.lower()}%"
        cond.append(or_(*[func.lower(c).like(like) for c in (audit_events.c.action, audit_events.c.actor_name,
                                                             audit_events.c.resource_id, audit_events.c.resource_kind)]))
    return cond


async def _project_titles(org_id: uuid.UUID, ids: set[uuid.UUID]) -> dict[str, str]:
    if not ids:
        return {}
    async with unscoped() as conn:
        await conn.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": str(org_id)})
        return {str(r.id): r.title for r in (await conn.execute(select(projects.c.id, projects.c.title).where(projects.c.id.in_(ids)))).all()}


async def search(ctx: RequestContext, q: AuditQuery) -> dict[str, Any]:
    q.validate()
    cond = and_(*_conditions(ctx, q))
    order = SORTS.get(q.sort, audit_events.c.seq)
    async with uow(ctx) as conn:
        total = (await conn.execute(select(func.count()).select_from(audit_events).where(cond))).scalar() or 0
        items = rows(await conn.execute(select(audit_events).where(cond)
                                        .order_by(order.desc() if q.direction == "desc" else order.asc(), audit_events.c.seq.desc())
                                        .offset((q.page - 1) * q.page_size).limit(q.page_size)))
        actors = [r[0] for r in (await conn.execute(select(audit_events.c.actor_name).where(audit_events.c.org_id == ctx.org_id)
                                                    .group_by(audit_events.c.actor_name).order_by(audit_events.c.actor_name).limit(200))).all()]
    titles = await _project_titles(ctx.org_id, {i["project_id"] for i in items if i["project_id"]})
    for i in items:
        i["summary"] = summarize(i, titles)
        i["project_title"] = titles.get(str(i["project_id"]), "")
    return {"items": items, "total": total, "page": q.page, "page_size": q.page_size, "pages": max(1, -(-total // q.page_size)),
            "categories": list(CATEGORIES), "actors": actors}

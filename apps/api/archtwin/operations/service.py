"""Operations module: AI usage & cost analytics, spend limits, system health, access inspection (org-admin views).

Every figure about spend is a SUM over the append-only `llm_calls` ledger (intelligence.usage). Members see only their own
calls (`view_own_usage`); `view_usage_all` sees the whole organization. Read-only except spend limits.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import and_, case, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from archtwin.audit import service as audit
from archtwin.common import authz
from archtwin.common.db import Principal, RequestContext, rows, unscoped, uow
from archtwin.common.errors import problem
from archtwin.common.schema import connectors, llm_calls, org_settings, outbox_events, projects, scan_runs, spend_limits, users
from archtwin.config import settings
from archtwin.connectors import service as csvc
from archtwin.connectors.adapters import git_repo
from archtwin.intelligence import usage

GROUPS = {"model": llm_calls.c.model, "operation": llm_calls.c.operation, "user": llm_calls.c.user_id, "project": llm_calls.c.project_id,
          "status": llm_calls.c.status}
GRANULARITY = {"day", "week", "month"}
MAX_DAYS = 400


@asynccontextmanager
async def _org_conn(org_id: uuid.UUID) -> AsyncIterator[Any]:
    async with unscoped() as conn:
        await conn.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": str(org_id)})
        yield conn


def _window(days: int) -> tuple[datetime, datetime, datetime]:
    days = max(1, min(int(days), MAX_DAYS))
    now = datetime.now(UTC)
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start - (now - start), start, now


def _scope(ctx: RequestContext, everyone: bool, project_id: uuid.UUID | None = None):
    cond = [llm_calls.c.org_id == ctx.org_id]
    if not everyone:
        cond.append(llm_calls.c.user_id == ctx.actor_id)
    if project_id:
        cond.append(llm_calls.c.project_id == project_id)
    return and_(*cond)


def _f(x: Any) -> float:
    return float(x or 0)


async def _kpis(conn, where) -> dict[str, Any]:
    r = (await conn.execute(select(
        func.coalesce(func.sum(llm_calls.c.cost_usd), 0).label("cost"),
        func.coalesce(func.sum(llm_calls.c.input_tokens + llm_calls.c.output_tokens), 0).label("tokens"),
        func.coalesce(func.sum(llm_calls.c.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(llm_calls.c.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(llm_calls.c.cached_input_tokens), 0).label("cached"),
        func.count().label("calls"),
        func.coalesce(func.sum(case((llm_calls.c.status != "ok", 1), else_=0)), 0).label("errors"),
        func.count(func.distinct(llm_calls.c.user_id)).label("active_users"),
        func.coalesce(func.avg(llm_calls.c.latency_ms), 0).label("avg_latency_ms")).where(where))).first()
    m = dict(r._mapping)
    return {"cost_usd": round(_f(m["cost"]), 6), "tokens": int(m["tokens"]), "input_tokens": int(m["input_tokens"]),
            "output_tokens": int(m["output_tokens"]), "cached_input_tokens": int(m["cached"]), "calls": int(m["calls"]),
            "errors": int(m["errors"]), "active_users": int(m["active_users"]), "avg_latency_ms": int(_f(m["avg_latency_ms"])),
            "cache_hit": round(int(m["cached"]) / int(m["input_tokens"]), 4) if int(m["input_tokens"]) else 0.0}


async def overview(ctx: RequestContext, days: int, everyone: bool) -> dict[str, Any]:
    prev_start, start, _ = _window(days)
    async with _org_conn(ctx.org_id) as conn:
        cur = await _kpis(conn, and_(_scope(ctx, everyone), llm_calls.c.created_at >= start))
        prev = await _kpis(conn, and_(_scope(ctx, everyone), llm_calls.c.created_at >= prev_start, llm_calls.c.created_at < start))
        day = func.date_trunc("day", llm_calls.c.created_at)
        daily = rows(await conn.execute(select(day.label("day"), llm_calls.c.operation, func.sum(llm_calls.c.cost_usd).label("cost"),
                                               func.sum(llm_calls.c.input_tokens + llm_calls.c.output_tokens).label("tokens"), func.count().label("calls"))
                                        .where(and_(_scope(ctx, everyone), llm_calls.c.created_at >= start)).group_by(day, llm_calls.c.operation)
                                        .order_by(day)))
        month = await _kpis(conn, and_(_scope(ctx, everyone), llm_calls.c.created_at >= usage.month_start()))
    limits = await usage.list_limits(ctx)
    if not everyone:
        mine = {"global", f"user:{ctx.actor_id}"}
        limits = [x for x in limits if x["subject"] in mine]
    return {"days": days, "everyone": everyone, "kpis": cur, "previous": prev, "month": month,
            "daily": [{"day": r["day"].date().isoformat(), "operation": r["operation"], "cost_usd": round(_f(r["cost"]), 6),
                       "tokens": int(r["tokens"] or 0), "calls": int(r["calls"])} for r in daily],
            "limits": await _label_subjects(ctx, limits), "prices": usage.price_table(), "warn_at": usage.WARN_AT}


async def breakdown(ctx: RequestContext, days: int, group_by: str, granularity: str, everyone: bool) -> dict[str, Any]:
    if group_by not in GROUPS or granularity not in GRANULARITY:
        raise problem(422, "AT-USAGE-001", "Invalid grouping", f"group_by in {sorted(GROUPS)}, granularity in {sorted(GRANULARITY)}")
    if group_by in ("user",) and not everyone:
        group_by = "model"
    _, start, _ = _window(days)
    col = GROUPS[group_by]
    bucket = func.date_trunc(granularity, llm_calls.c.created_at)
    where = and_(_scope(ctx, everyone), llm_calls.c.created_at >= start)
    async with _org_conn(ctx.org_id) as conn:
        series = rows(await conn.execute(select(bucket.label("bucket"), col.label("key"), func.sum(llm_calls.c.cost_usd).label("cost"),
                                                func.sum(llm_calls.c.input_tokens).label("input_tokens"),
                                                func.sum(llm_calls.c.output_tokens).label("output_tokens"), func.count().label("calls"))
                                         .where(where).group_by(bucket, col).order_by(bucket)))
        totals = rows(await conn.execute(select(col.label("key"), func.sum(llm_calls.c.cost_usd).label("cost"),
                                                func.sum(llm_calls.c.input_tokens).label("input_tokens"),
                                                func.sum(llm_calls.c.output_tokens).label("output_tokens"),
                                                func.sum(llm_calls.c.cached_input_tokens).label("cached"), func.count().label("calls"),
                                                func.sum(case((llm_calls.c.status != "ok", 1), else_=0)).label("errors"),
                                                func.avg(llm_calls.c.latency_ms).label("latency"))
                                         .where(where).group_by(col).order_by(func.sum(llm_calls.c.cost_usd).desc())))
    labels = await _labels(ctx, group_by, {str(t["key"]) for t in totals if t["key"] is not None})
    return {"group_by": group_by, "granularity": granularity, "days": days,
            "series": [{"bucket": r["bucket"].date().isoformat(), "key": str(r["key"]), "label": labels.get(str(r["key"]), str(r["key"])),
                        "cost_usd": round(_f(r["cost"]), 6), "input_tokens": int(r["input_tokens"] or 0),
                        "output_tokens": int(r["output_tokens"] or 0), "calls": int(r["calls"])} for r in series],
            "totals": [{"key": str(t["key"]), "label": labels.get(str(t["key"]), str(t["key"]) if t["key"] is not None else "—"),
                        "cost_usd": round(_f(t["cost"]), 6), "input_tokens": int(t["input_tokens"] or 0), "output_tokens": int(t["output_tokens"] or 0),
                        "cached_input_tokens": int(t["cached"] or 0), "calls": int(t["calls"]), "errors": int(t["errors"] or 0),
                        "avg_latency_ms": int(_f(t["latency"]))} for t in totals]}


async def _labels(ctx: RequestContext, group_by: str, keys: set[str]) -> dict[str, str]:
    ids = []
    for k in keys:
        try:
            ids.append(uuid.UUID(k))
        except ValueError:
            pass
    if not ids or group_by not in ("user", "project"):
        return {}
    async with unscoped() as conn:
        if group_by == "user":
            return {str(r["id"]): r["username"] for r in rows(await conn.execute(select(users.c.id, users.c.username).where(users.c.id.in_(ids))))}
        await conn.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": str(ctx.org_id)})
        return {str(r["id"]): r["title"] for r in rows(await conn.execute(select(projects.c.id, projects.c.title).where(
            and_(projects.c.id.in_(ids), projects.c.org_id == ctx.org_id))))}


async def labeled_limits(ctx: RequestContext) -> list[dict[str, Any]]:
    return await _label_subjects(ctx, await usage.list_limits(ctx))


async def _label_subjects(ctx: RequestContext, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    u = await _labels(ctx, "user", {i["subject"].split(":", 1)[1] for i in items if i["subject"].startswith("user:")})
    p = await _labels(ctx, "project", {i["subject"].split(":", 1)[1] for i in items if i["subject"].startswith("project:")})
    out = []
    for i in items:
        kind, _, ident = i["subject"].partition(":")
        out.append({**i, "kind": kind, "label": "Whole organization" if kind == "global" else (u if kind == "user" else p).get(ident, ident)})
    return out


async def export_csv(ctx: RequestContext, days: int, everyone: bool) -> str:
    _, start, _ = _window(days)
    async with _org_conn(ctx.org_id) as conn:
        rs = rows(await conn.execute(select(llm_calls.c.created_at, llm_calls.c.user_id, llm_calls.c.project_id, llm_calls.c.operation,
                                            llm_calls.c.model, llm_calls.c.input_tokens, llm_calls.c.cached_input_tokens, llm_calls.c.output_tokens,
                                            llm_calls.c.reasoning_tokens, llm_calls.c.cost_usd, llm_calls.c.cost_source, llm_calls.c.latency_ms,
                                            llm_calls.c.status, llm_calls.c.error_code)
                                     .where(and_(_scope(ctx, everyone), llm_calls.c.created_at >= start))
                                     .order_by(llm_calls.c.created_at).limit(200_000)))
    ul = await _labels(ctx, "user", {str(r["user_id"]) for r in rs if r["user_id"]})
    pl = await _labels(ctx, "project", {str(r["project_id"]) for r in rs if r["project_id"]})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time_utc", "user", "project", "operation", "model", "input_tokens", "cached_input_tokens", "output_tokens",
                "reasoning_tokens", "cost_usd", "cost_source", "latency_ms", "status", "error_code"])
    for r in rs:
        w.writerow([r["created_at"].isoformat(), ul.get(str(r["user_id"]), ""), pl.get(str(r["project_id"]), ""), r["operation"], r["model"],
                    r["input_tokens"], r["cached_input_tokens"], r["output_tokens"], r["reasoning_tokens"], f"{_f(r['cost_usd']):.6f}",
                    r["cost_source"], r["latency_ms"], r["status"], r["error_code"] or ""])
    async with uow(ctx) as conn:
        await audit.record(conn, ctx, "usage.export", "org", ctx.org_id, details={"days": days, "everyone": everyone, "rows": len(rs)})
    return buf.getvalue()


async def set_limits(ctx: RequestContext, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Upsert monthly caps; `monthly_usd: null` removes one. Subjects: global | user:<uuid> | project:<uuid> (same org)."""
    async with _org_conn(ctx.org_id) as conn:
        for it in items:
            subj = str(it["subject"]).strip()
            kind, _, ident = subj.partition(":")
            if kind not in ("global", "user", "project") or (kind == "global") != (ident == ""):
                raise problem(422, "AT-BUD-002", "Invalid subject", "global, user:<id> or project:<id>")
            if ident:
                uuid.UUID(ident)
            if kind == "project" and not (await conn.execute(select(projects.c.id).where(
                    and_(projects.c.id == uuid.UUID(ident), projects.c.org_id == ctx.org_id)))).first():
                raise problem(422, "AT-BUD-002", "Invalid subject", "project not in this organization")
            if it.get("monthly_usd") is None:
                await conn.execute(spend_limits.delete().where(and_(spend_limits.c.org_id == ctx.org_id, spend_limits.c.subject == subj)))
                continue
            v = Decimal(str(it["monthly_usd"]))
            if v < 0 or v > 1_000_000:
                raise problem(422, "AT-BUD-003", "Invalid amount", "0 – 1,000,000 USD")
            await conn.execute(pg_insert(spend_limits).values(org_id=ctx.org_id, subject=subj, monthly_usd=v, updated_by=ctx.actor_id)
                               .on_conflict_do_update(index_elements=["org_id", "subject"],
                                                      set_={"monthly_usd": v, "updated_by": ctx.actor_id, "updated_at": func.now()}))
    usage.invalidate(ctx.org_id)
    async with uow(ctx) as conn:
        await audit.record(conn, ctx, "spend_limits.update", "org", ctx.org_id, details={"items": [
            {"subject": i["subject"], "monthly_usd": i.get("monthly_usd")} for i in items]})
    return await _label_subjects(ctx, await usage.list_limits(ctx))


# ------------------------------------------------------------------ system health
async def _probe(name: str, coro) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        detail = await asyncio.wait_for(coro, 4)
        return {"name": name, "ok": True, "latency_ms": int((time.monotonic() - t0) * 1000), "detail": detail or ""}
    except Exception as e:  # noqa: BLE001
        return {"name": name, "ok": False, "latency_ms": int((time.monotonic() - t0) * 1000), "detail": type(e).__name__}


async def _http_ok(url: str, headers: dict | None = None) -> str:
    async with httpx.AsyncClient(timeout=3) as c:
        r = await c.get(url, headers=headers or {})
    if r.status_code >= 500:
        raise RuntimeError(f"HTTP {r.status_code}")
    return f"HTTP {r.status_code}"


async def _pg() -> str:
    async with unscoped() as conn:
        return str((await conn.execute(text("SHOW server_version"))).scalar())


async def _temporal() -> str:
    host, _, port = settings().temporal_address.partition(":")
    _, w = await asyncio.open_connection(host, int(port or 7233))
    w.close()
    return settings().temporal_address


async def _valkey() -> str:
    u = urlsplit(settings().valkey_url)
    _, w = await asyncio.open_connection(u.hostname, u.port or 6379)
    w.close()
    return "reachable"


async def system(ctx: RequestContext) -> dict[str, Any]:
    s = settings()
    probes = [_probe("PostgreSQL", _pg()), _probe("Cerbos (authorization)", authz.healthy()),
              _probe("Temporal (jobs)", _temporal()), _probe("Keycloak (OIDC)", _http_ok(s.oidc_jwks_url))]
    if s.llm_mode != "fake":
        probes.append(_probe("LiteLLM (AI gateway)", _http_ok(s.llm_base_url.rsplit("/v1", 1)[0] + "/health/liveliness")))
    if s.valkey_url:
        probes.append(_probe("Valkey (cache)", _valkey()))
    if s.s3_endpoint:
        probes.append(_probe("SeaweedFS (S3)", _http_ok(s.s3_endpoint)))
    if s.docling_url:
        probes.append(_probe("Docling (PDF/DOCX)", _http_ok(s.docling_url.rstrip("/") + "/health")))
    services = list(await asyncio.gather(*probes))
    for svc in services:
        if svc["name"].startswith("Cerbos"):
            svc["ok"] = svc["detail"] is not False and svc["ok"]
            svc["detail"] = "" if svc["ok"] else "unreachable"
    hour = datetime.now(UTC) - timedelta(hours=1)
    day = datetime.now(UTC) - timedelta(days=1)
    async with _org_conn(ctx.org_id) as conn:
        llm = (await conn.execute(select(func.count().label("calls"), func.coalesce(func.sum(case((llm_calls.c.status != "ok", 1), else_=0)), 0).label("errors"),
                                         func.percentile_cont(0.95).within_group(llm_calls.c.latency_ms).label("p95"),
                                         func.coalesce(func.sum(llm_calls.c.cost_usd), 0).label("cost"))
                                  .where(and_(llm_calls.c.org_id == ctx.org_id, llm_calls.c.created_at >= hour)))).first()
        scans = rows(await conn.execute(select(scan_runs.c.status, func.count().label("n")).where(and_(
            scan_runs.c.org_id == ctx.org_id, scan_runs.c.created_at >= day)).group_by(scan_runs.c.status)))
        backlog = (await conn.execute(select(func.count(), func.min(outbox_events.c.occurred_at)).where(and_(
            outbox_events.c.org_id == ctx.org_id, outbox_events.c.status == "pending")))).first()
        failing = rows(await conn.execute(select(connectors.c.name, connectors.c.kind, connectors.c.project_id, connectors.c.last_status)
                                          .where(and_(connectors.c.org_id == ctx.org_id, connectors.c.enabled.is_(True),
                                                      connectors.c.last_status.in_(("failed", "partial")))).limit(20)))
    pub = {"temporal_ui": f"http://localhost:{_env('TEMPORAL_UI_PORT', '8253')}", "langfuse": f"http://localhost:{_env('LANGFUSE_PORT', '3201')}",
           "litellm": f"http://localhost:{_env('LITELLM_PORT', '4200')}/ui", "keycloak": s.oidc_issuer.split("/realms/")[0] + "/admin/"}
    return {"services": services, "ok": all(x["ok"] for x in services), "llm_mode": s.llm_mode,
            "llm_last_hour": {"calls": int(llm.calls), "errors": int(llm.errors), "p95_latency_ms": int(_f(llm.p95)), "cost_usd": round(_f(llm.cost), 6)},
            "scans_last_day": {r["status"]: int(r["n"]) for r in scans},
            "outbox": {"pending": int(backlog[0] or 0), "oldest": backlog[1].isoformat() if backlog[1] else None},
            "connectors_attention": [{**r, "project_id": str(r["project_id"])} for r in failing],
            "egress": {"private_hosts": sorted(s.private_host_allowlist), "insecure_tls_hosts": sorted(s.insecure_tls_hosts),
                       "source_roots": s.source_roots},
            "consoles": pub}


def _env(k: str, d: str) -> str:
    import os
    return os.environ.get(k, d)


# ------------------------------------------------------------------ access inspection
ROLES = ["project_owner", "architect", "tech_lead", "contributor", "reviewer", "viewer"]
ORG_ROLES = ["org_owner", "org_admin", "member"]
MATRIX = {  # resource kind -> actions shown in the Roles & Permissions matrix (project-scoped)
    "project": ["view", "edit", "manage_members", "delete"],
    "connector": ["view", "create", "test", "scan", "delete", "write_external"],
    "architecture": ["view", "edit", "propose_baseline", "approve_baseline"],
    "diagram": ["view", "edit", "export"],
    "drift_finding": ["view", "triage", "suppress"],
    "adr": ["view", "create", "edit", "approve"],
    "document": ["view", "upload"],
    "assistant": ["ask", "draft"],
}
ORG_ACTIONS = ["view", "create_project", "view_own_usage", "view_usage_all", "manage_spend_limits", "view_system", "inspect_access",
               "view_audit", "export_audit", "manage"]
POLICY_DIRS = ("/policies", "deploy/cerbos/policies", "../../deploy/cerbos/policies")


def _sim(org_id: uuid.UUID, org_role: str, project_role: str | None, project_id: str) -> Principal:
    return Principal(user_id=uuid.UUID(int=0), subject="simulation", username=f"sim:{org_role}/{project_role or '-'}",
                     display_name="simulation", org_id=org_id, org_role=org_role,
                     project_roles={project_id: project_role} if project_role else {})


async def access_matrix(ctx: RequestContext) -> dict[str, Any]:
    """Effective permissions per role, decided by the live Cerbos PDP (simulated principals, nothing is granted)."""
    pid = str(uuid.UUID(int=1))
    attrs = {"org_id": str(ctx.org_id), "project_id": pid, "author_id": "someone-else", "writeback_enabled": False}

    async def row(org_role: str, prole: str | None) -> dict[str, Any]:
        p = _sim(ctx.org_id, org_role, prole, pid)
        res: dict[str, dict[str, bool]] = {}
        for kind, actions in MATRIX.items():
            res[kind] = await authz.check(p, kind, "sim", attrs, actions)
        res["org"] = await authz.check(p, "org", str(ctx.org_id), {"org_id": str(ctx.org_id)}, ORG_ACTIONS)
        return {"role": prole or org_role, "org_role": org_role, "project_role": prole, "decisions": res}
    rows_ = await asyncio.gather(*[row("member", r) for r in ROLES], row("org_admin", None), row("org_owner", None), row("member", None))
    async with uow(ctx) as conn:
        await audit.record(conn, ctx, "access.inspect", "org", ctx.org_id, details={"roles": len(rows_)})
    return {"resources": MATRIX, "org_actions": ORG_ACTIONS, "roles": list(rows_),
            "notes": {"author_rule": "Approve actions are evaluated for an item authored by someone else (separation of duties).",
                      "source": "Decisions come from the running Cerbos PDP with simulated principals."}}


def policy_files() -> dict[str, Any]:
    base = next((Path(d) for d in POLICY_DIRS if Path(d).is_dir()), None)
    if base is None:
        return {"files": [], "revision": "", "available": False}
    files = []
    for f in sorted(base.rglob("*.yaml")):
        body = f.read_text(encoding="utf-8", errors="replace")[:200_000]
        files.append({"path": str(f.relative_to(base)), "sha256": hashlib.sha256(body.encode()).hexdigest(), "content": body,
                      "lines": body.count("\n") + 1})
    rev = hashlib.sha256("".join(x["sha256"] for x in files).encode()).hexdigest()[:16]
    return {"files": files, "revision": rev, "available": True}


# ------------------------------------------------------------------ local source roots (System page)
async def source_roots(ctx: RequestContext) -> dict[str, Any]:
    wl = await csvc.org_source_roots(ctx.org_id)
    tok = git_repo.ORG_ROOTS.set(wl)
    try:
        eff = [str(p) for p in git_repo.allowed_roots()]
    finally:
        git_repo.ORG_ROOTS.reset(tok)
    return {"boundaries": settings().source_roots, "whitelist": wl, "effective": eff, "builtin": git_repo.BUILTIN_ROOT,
            "hint": "Folders can be whitelisted only inside a mounted boundary (ARCHTWIN_SOURCE_WORKSPACE, read-only)."}


async def set_source_roots(ctx: RequestContext, roots: list[str] | None) -> dict[str, Any]:
    if roots is not None:
        bounds = [Path(b).resolve() for b in settings().source_roots]
        clean: list[str] = []
        for r in roots[:50]:
            p = Path(str(r)).resolve()
            if not any(git_repo._under(p, b) for b in bounds):
                raise problem(422, "AT-CONN-005", "Not inside a mounted boundary",
                              f"{p} is not under {', '.join(map(str, bounds))}; mount it read-only via ARCHTWIN_SOURCE_WORKSPACE first")
            if not p.is_dir():
                raise problem(422, "AT-CONN-005", "Not a directory", str(p))
            clean.append(str(p))
        roots = sorted(set(clean))
    async with _org_conn(ctx.org_id) as conn:
        if roots is None:
            await conn.execute(org_settings.delete().where(and_(org_settings.c.org_id == ctx.org_id, org_settings.c.key == csvc.SOURCE_ROOTS_KEY)))
        else:
            await conn.execute(pg_insert(org_settings).values(org_id=ctx.org_id, key=csvc.SOURCE_ROOTS_KEY, value=roots, updated_by=ctx.actor_id)
                               .on_conflict_do_update(index_elements=["org_id", "key"],
                                                      set_={"value": roots, "updated_by": ctx.actor_id, "updated_at": func.now()}))
    async with uow(ctx) as conn:
        await audit.record(conn, ctx, "source_roots.update", "org", ctx.org_id, details={"roots": roots})
    return await source_roots(ctx)

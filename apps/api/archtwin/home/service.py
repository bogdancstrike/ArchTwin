"""Personal home: cross-project overview for the signed-in user.

Only projects the caller may view (Cerbos PlanResources via projects.list_projects) are visited, and each one is read
through its own RequestContext so PostgreSQL RLS still scopes every query. Modules that are off for a project contribute
nothing rather than fake zeros. No audit rows are exposed here (the audit trail stays admin-only).
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from archtwin.architecture import service as arch
from archtwin.common.db import RequestContext
from archtwin.connectors import service as connectors
from archtwin.decisions import service as decisions
from archtwin.drift import service as drift
from archtwin.flags import service as flags
from archtwin.inventory import service as inventory
from archtwin.projects import service as projects

MAX_PROJECTS = 60
SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
FRESH_RANK = {"current": 0, "stale": 1, "incomplete": 2, "unknown": 3}


def _ts(v: Any) -> str:
    return v.isoformat() if isinstance(v, datetime) else (v or "")


async def _project(c: RequestContext, p: dict[str, Any]) -> dict[str, Any]:
    pc = c.for_project(p["id"])
    on = {k: await flags.enabled(k, c.org_id, p["id"]) for k in
          ("module.architecture-graph", "module.drift-engine", "module.adr-workflow")}
    inv = await inventory.summary(pc)
    fresh = [x["freshness"]["status"] for x in inv["connectors"]]
    out: dict[str, Any] = {
        "id": p["id"], "title": p["title"], "purpose": p["purpose"], "tags": p["tags"], "my_role": p.get("my_role"),
        "connectors": len(inv["connectors"]),
        "freshness": max(fresh, key=lambda s: FRESH_RANK.get(s, 3)) if fresh else "unknown",
        "freshness_counts": {s: fresh.count(s) for s in set(fresh)},
        "snapshot": None, "drift": None, "adrs": None}
    attention: list[dict[str, Any]] = []
    activity: list[dict[str, Any]] = []
    for s in await connectors.recent_scans(pc, 5):
        activity.append({"kind": "scan", "project_id": p["id"], "project": p["title"], "at": _ts(s["finished_at"] or s["created_at"]),
                         "title": f"{s['connector']} scan {s['status']}", "status": s["status"],
                         "detail": f"{(s['stats'] or {}).get('observations', 0)} observations"
                                   + (f" @ {s['revision'][:10]}" if s["revision"] else "")})
    for x in inv["connectors"]:
        if x["freshness"]["status"] in ("stale", "incomplete"):
            attention.append({"kind": "connector", "severity": "medium", "project_id": p["id"], "project": p["title"],
                              "title": f"{x['name']} is {x['freshness']['status']}", "detail": x["freshness"].get("reason", ""),
                              "link": f"/projects/{p['id']}/inventory"})
    if on["module.architecture-graph"]:
        snaps = await arch.list_snapshots(pc, 1)
        if snaps:
            s = snaps[0]
            out["snapshot"] = {"version": s["version"], "nodes": s["node_count"], "edges": s["edge_count"], "at": _ts(s["created_at"])}
        for b in await arch.list_baselines(pc):
            if b["status"] == "proposed":
                mine = b["author_id"] == c.actor_id
                attention.append({"kind": "baseline", "severity": "high" if not mine else "low", "project_id": p["id"],
                                  "project": p["title"], "link": f"/projects/{p['id']}/architecture",
                                  "title": f"Baseline v{b['version']} awaiting review",
                                  "detail": "You proposed it; another reviewer must approve." if mine else (b["note"] or "Review and approve or reject.")})
            if b["decided_at"]:
                activity.append({"kind": "baseline", "project_id": p["id"], "project": p["title"], "at": _ts(b["decided_at"]),
                                 "title": f"Baseline v{b['version']} {b['status']}", "status": b["status"], "detail": b["note"]})
    if on["module.drift-engine"]:
        st = await drift.stats(pc)
        out["drift"] = {"open": st["open"], "unknown": st["unknown"],
                        "by_severity": {sev: sum(r["n"] for r in st["by"] if r["severity"] == sev and r["verdict"] == "drift")
                                        for sev in SEV_RANK}}
        for f in (await drift.list_findings(pc, status="open", verdict="drift"))[:5]:
            if f["severity"] in ("critical", "high"):
                attention.append({"kind": "drift", "severity": f["severity"], "project_id": p["id"], "project": p["title"],
                                  "title": f["title"], "detail": f["subject_key"], "link": f"/projects/{p['id']}/drift/{f['id']}"})
            activity.append({"kind": "drift", "project_id": p["id"], "project": p["title"], "at": _ts(f["first_seen"]),
                             "title": f"Drift: {f['title']}", "status": f["severity"], "detail": f["subject_key"]})
    if on["module.adr-workflow"]:
        adrs = await decisions.list_(pc)
        out["adrs"] = {"total": len(adrs), "proposed": sum(a["status"] == "proposed" for a in adrs),
                       "accepted": sum(a["status"] == "accepted" for a in adrs)}
        for a in adrs[:5]:
            if a["status"] == "proposed":
                attention.append({"kind": "adr", "severity": "medium", "project_id": p["id"], "project": p["title"],
                                  "title": f"ADR-{a['number']:04d} {a['title']} is proposed",
                                  "detail": "AI-drafted — needs a human decision." if a["ai_drafted"] else "Awaiting a decision.",
                                  "link": f"/projects/{p['id']}/decisions"})
            activity.append({"kind": "adr", "project_id": p["id"], "project": p["title"], "at": _ts(a["decided_at"] or a["created_at"]),
                             "title": f"ADR-{a['number']:04d} {a['title']}", "status": a["status"], "detail": ""})
    out["last_activity"] = max((a["at"] for a in activity), default=_ts(p["created_at"]))
    return {"project": out, "attention": attention, "activity": activity}


async def home(c: RequestContext) -> dict[str, Any]:
    ps = (await projects.list_projects(c))[:MAX_PROJECTS]
    sem = asyncio.Semaphore(6)

    async def one(p):
        async with sem:
            return await _project(c, p)
    parts = await asyncio.gather(*(one(p) for p in ps))
    attention = sorted((a for x in parts for a in x["attention"]), key=lambda a: SEV_RANK.get(a["severity"], 4))
    activity = sorted((a for x in parts for a in x["activity"]), key=lambda a: a["at"], reverse=True)[:25]
    prj = sorted((x["project"] for x in parts), key=lambda p: p["last_activity"], reverse=True)
    totals = {"projects": len(prj), "connectors": sum(p["connectors"] for p in prj),
              "elements": sum((p["snapshot"] or {}).get("nodes", 0) for p in prj),
              "relationships": sum((p["snapshot"] or {}).get("edges", 0) for p in prj),
              "drift_open": sum((p["drift"] or {}).get("open", 0) for p in prj),
              "unknown": sum((p["drift"] or {}).get("unknown", 0) for p in prj),
              "adrs": sum((p["adrs"] or {}).get("total", 0) for p in prj),
              "stale_connectors": sum(v for p in prj for k, v in p["freshness_counts"].items() if k in ("stale", "incomplete"))}
    return {"generated_at": datetime.now(UTC).isoformat(), "totals": totals, "projects": prj,
            "attention": attention[:20], "activity": activity}

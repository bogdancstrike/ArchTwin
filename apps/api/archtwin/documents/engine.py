"""Documentation engine (AT-DOCUMENTATION_ENGINE-001..003): document types from `doctypes.DOC_TYPES` over a snapshot.

Evidence documents are Jinja2 templates where every generated statement cites evidence IDs (coverage report); AI documents
are drafted by `ai_writer` from the same cited facts. Regeneration yields a reviewable diff; hand-edited sections survive."""
from __future__ import annotations

import difflib
import re
import uuid
from typing import Any

from jinja2 import Environment, select_autoescape
from sqlalchemy import and_, func, select

from archtwin.architecture import flows as flows_mod
from archtwin.architecture import service as arch
from archtwin.audit import service as audit
from archtwin.common.db import RequestContext, row, rows, uow
from archtwin.common.errors import not_found, problem
from archtwin.common.ids import new_id
from archtwin.common.schema import generated_docs
from archtwin.decisions import service as decisions
from archtwin.documents import ai_writer
from archtwin.documents.citations import evidence_section
from archtwin.documents.doctypes import DOC_TYPES, DocType

MANUAL_RX = re.compile(r"<!-- archtwin:manual:(?P<id>[\w\-]+) -->(?P<body>.*?)<!-- /archtwin:manual -->", re.DOTALL)
env = Environment(autoescape=select_autoescape(default=False), trim_blocks=True, lstrip_blocks=True)
env.filters["md"] = lambda s: re.sub(r"([\\`*_{}\[\]<>|])", r"\\\1", str(s or ""))   # Markdown-escape untrusted names

def _context(g: dict[str, Any], title: str, snap: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    nodes, edges = g["nodes"], g["edges"]
    evidence: list[dict[str, Any]] = []

    def ref(x: dict[str, Any]) -> str:
        evs = x.get("evidence") or []
        if not evs:
            return "no evidence"
        evidence.append({"id": f"E{len(evidence) + 1}", "key": x["key"], **evs[0]})
        return f"E{len(evidence)}"

    contains = {}
    for e in edges.values():
        if e["kind"] == "contains":
            contains.setdefault(e["source"], []).append(e["target"])
    systems = []
    for k, n in sorted(nodes.items()):
        if n["kind"] == "software-system" and contains.get(k):
            cs = [c for c in contains[k] if nodes.get(c, {}).get("kind") == "container"]
            ext = sorted({nodes[e["target"]]["name"] for e in edges.values() if e["source"] in cs and nodes.get(e["target"], {}).get("kind") == "external-system"})
            systems.append({"name": n["name"], "containers": cs, "externals": ext, "ref": ref(n)})
    containers = []
    for k, n in sorted(nodes.items()):
        if n["kind"] != "container":
            continue
        out = [{"target": nodes[e["target"]]["name"], "kind": e["kind"], "protocol": e["attributes"].get("protocol"), "ref": ref(e)}
               for e in sorted(edges.values(), key=lambda e: e["key"]) if e["source"] == k and e["kind"] in ("calls", "writes", "reads", "publishes", "consumes")
               and e["target"] in nodes]
        comps = sorted(nodes[c]["name"] for c in contains.get(k, []) if nodes.get(c, {}).get("kind") == "component")
        containers.append({"name": n["name"], "tech": n["attributes"].get("technology", ""), "origins": n["origins"],
                           "confidence": n["confidence"], "owner": n["attributes"].get("owner", ""), "ref": ref(n),
                           "outgoing": out, "components": comps})
    externals = [{"name": n["name"], "kind": n["kind"], "inferred": n.get("inferred_only"), "ref": ref(n)}
                 for k, n in sorted(nodes.items()) if n["kind"] in ("external-system", "person")]
    endpoints = []
    for e in sorted(edges.values(), key=lambda e: e["key"]):
        if e["kind"] == "exposes" and e["target"] in nodes and nodes[e["target"]]["kind"] == "api-endpoint":
            t = nodes[e["target"]]
            endpoints.append({"container": nodes.get(e["source"], {}).get("name", e["source"]), "method": t["attributes"].get("method", ""),
                              "path": t["attributes"].get("path", ""), "ref": ref(t)})
    tables = []
    for k, n in sorted(nodes.items()):
        if n["kind"] != "table":
            continue
        a = n["attributes"]
        decl = a.get("declared_in") or []
        tables.append({"name": n["name"], "owner": a.get("owner", ""), "columns": a.get("columns") or [], "ref": ref(n),
                       "source": f"Declared in `{decl[0]['path']}` ({decl[0]['kind']})" if decl else f"Observed in database catalog `{n['evidence'][0].get('source_ref', '') if n.get('evidence') else ''}`"})
    flows = []
    for f in flows_mod.recognize(g)["flows"]:
        names = {p["key"]: p["name"] for p in f["participants"]}
        ids = {p["key"]: f"P{i}" for i, p in enumerate(f["participants"])}
        steps = [{**st, "from_name": names.get(st["from"], st["from"]), "to_name": names.get(st["to"], st["to"]),
                  "from_id": ids.get(st["from"]), "to_id": ids.get(st["to"]), "ref": ref(edges[st["edge"]]) if st["edge"] in edges else "no evidence"}
                 for st in f["steps"]]
        flows.append({**f, "steps": steps})
    code_containers = []
    for k, n in sorted(nodes.items()):
        if n["kind"] != "container":
            continue
        comps = []
        for ck in sorted(c for c in contains.get(k, []) if nodes.get(c, {}).get("kind") == "component"):
            cn = nodes[ck]
            code = [{"name": nodes[x]["name"], "ref": ref(nodes[x]), **nodes[x]["attributes"]}
                    for x in sorted(contains.get(ck, [])) if nodes.get(x, {}).get("kind") == "code"]
            comps.append({"module": cn["attributes"].get("module", cn["name"]), "path": cn["attributes"].get("path", ""), "code": code[:60]})
        eps = [nodes[e["target"]]["attributes"] for e in edges.values() if e["source"] == k and e["kind"] == "exposes" and e["target"] in nodes]
        if comps or eps:
            code_containers.append({"name": n["name"], "tech": n["attributes"].get("technology", ""), "ref": ref(n), "components": comps,
                                    "endpoints": sorted(eps, key=lambda x: (x.get("path", ""), x.get("method", ""))),
                                    "entrypoints": sorted({ep for c in comps for ep in (nodes.get(f"component:{k.split(':', 1)[1]}/{c['module']}", {})
                                                                                         .get("attributes", {}).get("entrypoints") or [])})})
    repo_adrs = [{"number": "—", "title": n["name"], "status": "imported", "source": n["attributes"].get("path", ""), "ref": ref(n)}
                 for k, n in sorted(nodes.items()) if n["kind"] == "adr"]
    total = len(containers) + len(externals) + len(systems)
    cited = sum(1 for x in containers + externals + systems if x["ref"] != "no evidence")
    coverage = {"elements": total, "cited": cited, "ratio": round(cited / total, 3) if total else 1.0,
                "uncited": [x["name"] for x in containers + externals + systems if x["ref"] == "no evidence"]}
    return ({"title": title, "snap": snap, "systems": systems, "containers": containers, "externals": externals,
             "endpoints": endpoints[:2000], "tables": tables, "flows": flows[:40], "code_containers": code_containers,
             "adrs": repo_adrs, "app_adrs": []}, evidence, coverage)


def merge_manual(previous: str | None, new: str) -> str:
    """Keep hand-edited sections from the previous version (matched by id)."""
    if not previous:
        return new
    kept = {m.group("id"): m.group(0) for m in MANUAL_RX.finditer(previous)}
    return MANUAL_RX.sub(lambda m: kept.get(m.group("id"), m.group(0)), new)


def doc_type(key: str) -> DocType:
    if key not in DOC_TYPES:
        raise problem(422, "AT-DOCS-001", "Unknown document type", ", ".join(DOC_TYPES))
    return DOC_TYPES[key]


def render(template: str, g: dict[str, Any], title: str, snap: dict[str, Any], extra: dict[str, Any] | None = None
           ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Evidence documents only (deterministic)."""
    dt = doc_type(template)
    if dt.mode != "evidence":
        raise problem(422, "AT-DOCS-003", "Not an evidence document", template)
    ctx, evidence, coverage = _context(g, title, snap)
    ctx.update(extra or {})
    body = env.from_string(dt.template).render(**ctx)
    used = {m for m in re.findall(r"\[(E\d+)\]", body)}
    evidence = [e for e in evidence if e["id"] in used]
    return body + evidence_section(evidence), evidence, coverage


async def generate(ctx: RequestContext, template: str, title: str) -> dict[str, Any]:
    async with uow(ctx) as conn:
        snap = await arch.resolve_snapshot(conn, ctx)
        if not snap:
            raise problem(409, "AT-DOCS-002", "No snapshot", "Scan a connector first.")
        g = await arch.load_graph(conn, snap["id"])
        prev = row((await conn.execute(select(generated_docs).where(and_(generated_docs.c.project_id == ctx.project_id,
                                                                         generated_docs.c.template == template))
                                       .order_by(generated_docs.c.version.desc()).limit(1))).first())
    dt = doc_type(template)
    if dt.mode == "ai":
        body, evidence, coverage = await ai_writer.write(ctx, dt, g, title, snap, _context(g, title, snap))
    else:
        extra = {"app_adrs": [{"number": f"{a['number']:04d}", "title": a["title"], "status": a["status"], "source": "ArchTwin", "ref": ""}
                              for a in await decisions.list_(ctx)]} if template == "decision-log" else None
        body, evidence, coverage = render(template, g, title, snap, extra)
    async with uow(ctx) as conn:
        body = merge_manual(prev["content"] if prev else None, body)
        if prev and prev["content"] == body:
            return {**prev, "diff": "", "unchanged": True}
        v = (prev["version"] + 1) if prev else 1
        did = new_id()
        await conn.execute(generated_docs.insert().values(id=did, org_id=ctx.org_id, project_id=ctx.project_id, template=template,
                                                          version=v, snapshot_id=snap["id"], content=body, evidence=evidence,
                                                          coverage=coverage, created_by=ctx.actor_id))
        await audit.record(conn, ctx, "docs.generate", "document", did, details={"template": template, "version": v})
        diff = "".join(difflib.unified_diff((prev["content"] if prev else "").splitlines(True), body.splitlines(True),
                                            fromfile=f"v{v - 1}", tofile=f"v{v}", n=2)) if prev else ""
        return {**row((await conn.execute(select(generated_docs).where(generated_docs.c.id == did))).first()), "diff": diff[:200_000]}


async def save_manual(ctx: RequestContext, doc_id: uuid.UUID, content: str) -> dict[str, Any]:
    """Hand edits are only accepted inside manual sections; everything else stays generated."""
    async with uow(ctx) as conn:
        d = row((await conn.execute(select(generated_docs).where(generated_docs.c.id == doc_id))).first())
        if not d:
            raise not_found("document")
        merged = MANUAL_RX.sub(lambda m: next((x.group(0) for x in MANUAL_RX.finditer(content) if x.group("id") == m.group("id")), m.group(0)), d["content"])
        v = (await conn.execute(select(func.max(generated_docs.c.version)).where(and_(generated_docs.c.project_id == ctx.project_id,
                                                                                     generated_docs.c.template == d["template"])))).scalar() + 1
        nid = new_id()
        await conn.execute(generated_docs.insert().values(id=nid, org_id=ctx.org_id, project_id=ctx.project_id, template=d["template"],
                                                          version=v, snapshot_id=d["snapshot_id"], content=merged, evidence=d["evidence"],
                                                          coverage=d["coverage"], created_by=ctx.actor_id))
        await audit.record(conn, ctx, "docs.manual_edit", "document", nid)
        return row((await conn.execute(select(generated_docs).where(generated_docs.c.id == nid))).first())


async def list_generated(ctx: RequestContext) -> list[dict[str, Any]]:
    async with uow(ctx) as conn:
        return rows(await conn.execute(select(generated_docs.c.id, generated_docs.c.template, generated_docs.c.version,
                                              generated_docs.c.created_at, generated_docs.c.coverage)
                                       .where(generated_docs.c.project_id == ctx.project_id).order_by(generated_docs.c.template,
                                                                                                     generated_docs.c.version.desc())))


async def get_generated(ctx: RequestContext, doc_id: uuid.UUID) -> dict[str, Any]:
    async with uow(ctx) as conn:
        d = row((await conn.execute(select(generated_docs).where(generated_docs.c.id == doc_id))).first())
    if not d:
        raise not_found("document")
    return d

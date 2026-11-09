"""Documentation engine (AT-DOCUMENTATION_ENGINE-001..003): document types from `doctypes.DOC_TYPES` over a snapshot.

Evidence documents are Jinja2 templates where every generated statement cites evidence IDs (coverage report); they are
exhaustive — every system, container, endpoint, table and flow, never a top-N. AI documents are drafted section by
section by `ai_writer` from the same cited facts. Regeneration yields a reviewable diff; hand-edited sections survive."""
from __future__ import annotations

import difflib
import re
import uuid
from typing import Any

from jinja2 import Environment, select_autoescape
from markupsafe import Markup
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
from archtwin.documents.features import FeatureIndex, flowchart, mermaid_id, mermaid_label

MANUAL_RX = re.compile(r"<!-- archtwin:manual:(?P<id>[\w\-]+) -->(?P<body>.*?)<!-- /archtwin:manual -->", re.DOTALL)
env = Environment(autoescape=select_autoescape(default=False), trim_blocks=True, lstrip_blocks=True)
env.filters["md"] = lambda s: re.sub(r"([\\`*_{}\[\]<>|])", r"\\\1", str(s or ""))   # Markdown-escape untrusted names
# Inside backticks the Markdown renderer escapes everything itself, so HTML-escaping would show entities literally.
env.filters["code"] = lambda s: Markup(str(s or "").replace("`", "'").replace("\n", " "))
env.filters["mm"] = lambda s, n=60: Markup(mermaid_label(s, n))                       # Mermaid-safe label (quotes/brackets removed)
env.filters["anchor"] = lambda s: re.sub(r"[^a-z0-9_\- ]", "", str(s or "").lower()).strip().replace(" ", "-")

RELATIONS = ("calls", "writes", "reads", "publishes", "consumes")
MAX_FLOW_DIAGRAMS = 60          # every flow is documented; only the most significant ones also get a sequence diagram
NON_ENDPOINT_FEATURE = {"data": "Data access", "request": "Service-to-service requests", "event": "Events and messaging"}
VERBS = {"calls": "calls", "forwards": "forwards to", "uses": "uses", "handles": "is handled by", "reads": "reads from",
         "writes": "writes to", "publishes": "publishes to", "consumes": "consumes from"}


def _loc(n: dict[str, Any]) -> str:
    a = n.get("attributes", {})
    if a.get("path") and a.get("line_start"):
        return f"{a['path']}:{a['line_start']}"
    for ev in n.get("evidence") or []:
        span = ev.get("span") or {}
        path = span.get("path") or ev.get("source_ref") or ""
        if path:
            return f"{path}:{span['line_start']}" if span.get("line_start") else path
    return ""


def describe_flow(f: dict[str, Any], names: dict[str, str]) -> str:
    """One deterministic sentence: the hops in order and the systems it spans."""
    st = f["steps"]
    if not st:
        return ""
    hops = [f"{names.get(s['from'], s['from'])} {VERBS.get(s['kind'], s['kind'])} {names.get(s['to'], s['to'])}" for s in st[:12]]
    more = f" (+{len(st) - 12} more steps)" if len(st) > 12 else ""
    across = f" It spans {', '.join(f['systems'])}." if f.get("distributed") else ""
    return "; then ".join(hops) + more + "." + across


def _context(g: dict[str, Any], title: str, snap: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    nodes, edges = g["nodes"], g["edges"]
    evidence: list[dict[str, Any]] = []
    cited: dict[str, str] = {}

    def ref(x: dict[str, Any]) -> str:
        if x["key"] in cited:
            return cited[x["key"]]
        evs = x.get("evidence") or []
        if not evs:
            return "no evidence"
        evidence.append({"id": f"E{len(evidence) + 1}", "key": x["key"], **evs[0]})
        cited[x["key"]] = f"E{len(evidence)}"
        return cited[x["key"]]

    contains: dict[str, list[str]] = {}
    parent: dict[str, str] = {}
    for e in edges.values():
        if e["kind"] == "contains":
            contains.setdefault(e["source"], []).append(e["target"])
            parent[e["target"]] = e["source"]
    exposes = {e["target"]: e["source"] for e in edges.values() if e["kind"] == "exposes"}
    eps_all = [k for k, n in nodes.items() if n["kind"] == "api-endpoint"]

    def ep_label(n: dict[str, Any]) -> str:
        a = n.get("attributes", {})
        return f"{a.get('method', '')} {a.get('path', '')}".strip() or n.get("name", "")

    fx = FeatureIndex(ep_label(nodes[k]) for k in eps_all)

    def system_of(k: str) -> str:
        seen: set[str] = set()
        while k in parent and k not in seen:
            seen.add(k)
            k = parent[k]
            if nodes.get(k, {}).get("kind") == "software-system":
                return nodes[k]["name"]
        return ""

    systems = []
    for k, n in sorted(nodes.items()):
        if n["kind"] == "software-system" and contains.get(k):
            cs = [c for c in contains[k] if nodes.get(c, {}).get("kind") == "container"]
            ext = sorted({nodes[e["target"]]["name"] for e in edges.values() if e["source"] in cs and nodes.get(e["target"], {}).get("kind") == "external-system"})
            systems.append({"key": k, "name": n["name"], "containers": cs, "container_names": sorted(nodes[c]["name"] for c in cs),
                            "externals": ext, "ref": ref(n), "repository": n["attributes"].get("repository", "")})
    endpoints = []
    for k in sorted(eps_all, key=lambda k: (exposes.get(k, ""), nodes[k]["attributes"].get("path", ""), nodes[k]["attributes"].get("method", ""))):
        t, a = nodes[k], nodes[k]["attributes"]
        owner = exposes.get(k, "")
        endpoints.append({"key": k, "container": nodes.get(owner, {}).get("name", owner or "unknown"), "container_key": owner,
                          "system": system_of(owner) if owner else "", "method": a.get("method", ""), "path": a.get("path", "") or t["name"],
                          "handler": ".".join(x for x in (a.get("module", ""), a.get("handler", "")) if x), "loc": _loc(t),
                          "feature": fx.of(ep_label(t)), "params": re.findall(r"\{([^}]+)\}", a.get("path", "")),
                          "routes_to": a.get("routes_to", ""), "description": a.get("description", ""),
                          "body": a.get("method", "") in ("POST", "PUT", "PATCH"), "ref": ref(t)})
    by_container: dict[str, list[dict[str, Any]]] = {}
    for e in endpoints:
        by_container.setdefault(e["container_key"], []).append(e)
    containers = []
    for k, n in sorted(nodes.items()):
        if n["kind"] != "container":
            continue
        a = n["attributes"]
        out = [{"target": nodes[e["target"]]["name"], "kind": e["kind"], "protocol": e["attributes"].get("protocol"), "ref": ref(e)}
               for e in sorted(edges.values(), key=lambda e: e["key"]) if e["source"] == k and e["kind"] in RELATIONS and e["target"] in nodes]
        inc = [{"source": nodes[e["source"]]["name"], "kind": e["kind"], "protocol": e["attributes"].get("protocol"), "ref": ref(e)}
               for e in sorted(edges.values(), key=lambda e: e["key"]) if e["target"] == k and e["kind"] in RELATIONS and e["source"] in nodes]
        comps = sorted((nodes[c] for c in contains.get(k, []) if nodes.get(c, {}).get("kind") == "component"), key=lambda c: c["name"])
        containers.append({"key": k, "name": n["name"], "tech": a.get("technology", ""), "origins": n["origins"], "system": system_of(k),
                           "confidence": n["confidence"], "owner": a.get("owner", ""), "ref": ref(n), "subtype": a.get("subtype", ""),
                           "image": a.get("image", ""), "ports": a.get("ports") or [], "compose_file": a.get("compose_file", ""),
                           "profiles": a.get("profiles") or [], "outgoing": out, "incoming": inc, "components": [c["name"] for c in comps],
                           "component_details": [{"name": c["name"], "path": c["attributes"].get("path", ""), "modules": c["attributes"].get("modules", 0),
                                                  "ref": ref(c)} for c in comps],
                           "endpoints": by_container.get(k, []), "features": sorted({e["feature"] for e in by_container.get(k, [])})})
    externals = [{"name": n["name"], "kind": n["kind"], "inferred": n.get("inferred_only"), "ref": ref(n),
                  "technology": n["attributes"].get("technology", ""), "used_by": n["attributes"].get("used_by", "")}
                 for k, n in sorted(nodes.items()) if n["kind"] in ("external-system", "person")]
    databases = [{"name": n["name"], "technology": n["attributes"].get("technology", ""), "used_by": n["attributes"].get("used_by", ""), "ref": ref(n)}
                 for k, n in sorted(nodes.items()) if n["kind"] == "database"]
    tables = []
    for k, n in sorted(nodes.items()):
        if n["kind"] != "table":
            continue
        a = n["attributes"]
        decl = a.get("declared_in") or []
        tables.append({"name": n["name"], "owner": a.get("owner", ""), "columns": a.get("columns") or [], "ref": ref(n),
                       "source": f"Declared in `{decl[0]['path']}` ({decl[0]['kind']})" if decl
                       else f"Observed in database catalog `{n['evidence'][0].get('source_ref', '') if n.get('evidence') else ''}`"})
    names = {k: n["name"] for k, n in nodes.items()}
    flows = []
    for f in flows_mod.recognize(g)["flows"]:
        pnames = {p["key"]: p["name"] for p in f["participants"]}
        ids = {p["key"]: f"P{i}" for i, p in enumerate(f["participants"])}
        steps = [{**st, "from_name": pnames.get(st["from"], st["from"]), "to_name": pnames.get(st["to"], st["to"]),
                  "from_id": ids.get(st["from"]), "to_id": ids.get(st["to"]), "ref": ref(edges[st["edge"]]) if st["edge"] in edges else "no evidence"}
                 for st in f["steps"]]
        ep = nodes.get(f.get("endpoint") or f.get("entry") or "", {})
        feature = fx.of(ep_label(ep)) if ep.get("kind") == "api-endpoint" else \
            NON_ENDPOINT_FEATURE.get(f["kind"]) or fx.of(f["name"])
        flows.append({**f, "steps": steps, "feature": feature,
                      "description": describe_flow(f, {**names, **pnames}),
                      "components": [p["name"] for p in f["participants"] if p["kind"] in ("component", "container")],
                      "data": [p["name"] for p in f["participants"] if p["kind"] in ("database", "table", "kafka-topic", "external-system")
                               or p.get("subtype") in ("storage", "database")],
                      "entry_name": f["participants"][0]["name"] if f["participants"] else "",
                      "first_ref": next((s["ref"] for s in steps if s["ref"] != "no evidence"), "no evidence")})
    features: dict[str, dict[str, Any]] = {}
    for e in endpoints:
        ft = features.setdefault(e["feature"], {"name": e["feature"], "endpoints": [], "flows": [], "containers": set()})
        ft["endpoints"].append(e)
        ft["containers"].add(e["container"])
    for f in flows:
        ft = features.setdefault(f["feature"], {"name": f["feature"], "endpoints": [], "flows": [], "containers": set()})
        ft["flows"].append(f)
    feature_list = [{**v, "containers": sorted(v["containers"])}
                    for _, v in sorted(features.items(), key=lambda kv: (kv[0] in NON_ENDPOINT_FEATURE.values(),
                                                                         -len(kv[1]["endpoints"]) - len(kv[1]["flows"]), kv[0]))]
    rank = {f["name"]: i for i, f in enumerate(feature_list)}
    flows.sort(key=lambda f: (rank[f["feature"]], not f["distributed"], f["name"]))      # document order = feature order
    for i, f in enumerate(flows, 1):
        f["order"] = i
    for ft in feature_list:
        ft["flows"].sort(key=lambda f: f["order"])
    diagrammed = {f["id"] for f in sorted(flows, key=lambda f: (not f["distributed"], -f["length"]))[:MAX_FLOW_DIAGRAMS]}
    for f in flows:
        f["diagram"] = f["id"] in diagrammed
    code_containers = []
    for k, n in sorted(nodes.items()):
        if n["kind"] != "container":
            continue
        comps = []
        for ck in sorted(c for c in contains.get(k, []) if nodes.get(c, {}).get("kind") == "component"):
            cn = nodes[ck]
            code = [{"name": nodes[x]["name"], "ref": ref(nodes[x]), **nodes[x]["attributes"]}
                    for x in sorted(contains.get(ck, [])) if nodes.get(x, {}).get("kind") == "code"]
            comps.append({"module": cn["attributes"].get("module", cn["name"]), "path": cn["attributes"].get("path", ""), "code": code[:400]})
        eps = [nodes[e["target"]]["attributes"] for e in edges.values() if e["source"] == k and e["kind"] == "exposes" and e["target"] in nodes]
        if comps or eps:
            code_containers.append({"name": n["name"], "tech": n["attributes"].get("technology", ""), "ref": ref(n), "components": comps,
                                    "endpoints": sorted(eps, key=lambda x: (x.get("path", ""), x.get("method", ""))),
                                    "entrypoints": sorted({ep for c in comps for ep in (nodes.get(f"component:{k.split(':', 1)[1]}/{c['module']}", {})
                                                                                         .get("attributes", {}).get("entrypoints") or [])})})
    repo_adrs = [{"number": "—", "title": n["name"], "status": "imported", "source": n["attributes"].get("path", ""), "ref": ref(n)}
                 for k, n in sorted(nodes.items()) if n["kind"] == "adr"]
    tech: dict[str, set[str]] = {}
    for c in containers:
        for t in [c["tech"], *[b for b in (nodes[c["key"]]["attributes"].get("base_images") or []) if ":" in b]]:
            if t:
                tech.setdefault(t, set()).add(c["name"])
    for x in externals + databases:
        if x.get("technology"):
            tech.setdefault(x["technology"], set()).add(x.get("used_by") or x["name"])
    stats = {"components": sum(len(c["components"]) for c in containers), "distributed_flows": sum(f["distributed"] for f in flows),
             "code_elements": sum(1 for n in nodes.values() if n["kind"] == "code")}
    total = len(containers) + len(externals) + len(systems)
    cited_n = sum(1 for x in containers + externals + systems if x["ref"] != "no evidence")
    coverage = {"elements": total, "cited": cited_n, "ratio": round(cited_n / total, 3) if total else 1.0,
                "uncited": [x["name"] for x in containers + externals + systems if x["ref"] == "no evidence"],
                "endpoints": len(endpoints), "flows": len(flows), "tables": len(tables)}
    return ({"title": title, "snap": snap, "systems": systems, "containers": containers, "externals": externals, "databases": databases,
             "endpoints": endpoints, "tables": tables, "flows": flows, "features": feature_list, "code_containers": code_containers,
             "adrs": repo_adrs, "app_adrs": [], "stats": stats, "technologies": [{"name": k, "used_by": sorted(v)} for k, v in sorted(tech.items())],
             "key_flows": sorted(flows, key=lambda f: (not f["distributed"], -f["length"]))[:15],
             "diagrams": _diagrams(systems, containers, externals, tables, edges)},
            evidence, coverage)


def _diagrams(systems: list[dict], containers: list[dict], externals: list[dict], tables: list[dict], edges: dict[str, dict]) -> dict[str, str]:
    sys_id = {s["key"]: f"S{i}" for i, s in enumerate(systems)}
    xid = {x["name"]: f"X{i}" for i, x in enumerate(externals) if x["kind"] == "external-system"}
    context = flowchart([("user", "User", "person")] + [(sys_id[s["key"]], s["name"], "box") for s in systems]
                        + [(v, k, "ext") for k, v in xid.items()],
                        [("user", sys_id[s["key"]], "uses") for s in systems[:12]]
                        + sorted({(sys_id[s["key"]], xid[x], "calls") for s in systems for x in s["externals"] if x in xid}))
    shown = containers[:40]
    cid = {c["key"]: f"C{i}" for i, c in enumerate(shown)}
    cont = flowchart([(cid[c["key"]], f"{c['name']}{' · ' + c['tech'] if c['tech'] else ''}",
                       "db" if c["subtype"] in ("database", "storage") else "box") for c in shown],
                     sorted({(cid[e["source"]], cid[e["target"]], e["kind"]) for e in edges.values()
                             if e["kind"] in RELATIONS and e["source"] in cid and e["target"] in cid}))
    er = ["erDiagram"]
    tnames = {t["name"].split(".")[-1].lower(): mermaid_id(t["name"]) for t in tables}
    for t in tables[:60]:
        er.append(f"  {mermaid_id(t['name'])} {{")
        for c in t["columns"][:30]:
            typ = mermaid_id(str(c.get("type") or "any").split("(")[0]) or "any"
            er.append(f"    {typ} {mermaid_id(c['name'])}{' PK' if c.get('primary_key') else ''}")
        er.append("  }")
    for t in tables[:60]:
        for c in t["columns"]:
            target = str(c.get("references") or "").split(".")[0].lower()
            if target in tnames:
                er.append(f'  {tnames[target]} ||--o{{ {mermaid_id(t["name"])} : "{mermaid_label(c["name"], 20)}"')
    return {"context": context, "containers": cont, "er": "\n".join(er) if len(er) > 1 else ""}


def tidy(md: str) -> str:
    """Markdown hygiene after templating: a blank line before and after headings and fences (outside code), no runs of blanks."""
    out: list[str] = []
    in_code = False
    for ln in md.splitlines():
        fence = ln.lstrip().startswith("```")
        heading = not in_code and re.match(r"^#{1,6} ", ln) is not None
        if (heading or (fence and not in_code)) and out and out[-1].strip():
            out.append("")
        if out and not in_code and out[-1].startswith("#") and re.match(r"^#{1,6} ", out[-1]) and ln.strip():
            out.append("")
        out.append(ln)
        if fence:
            in_code = not in_code
            if not in_code:
                out.append("")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


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
    body = tidy(env.from_string(dt.template).render(**ctx))
    used = {m for m in re.findall(r"\[(E\d+)\]", body)}
    evidence = [e for e in evidence if e["id"] in used]
    return body + evidence_section(evidence), evidence, coverage


async def _app_adrs(ctx: RequestContext) -> list[dict[str, Any]]:
    return [{"number": f"{a['number']:04d}", "title": a["title"], "status": a["status"], "source": "ArchTwin", "ref": "",
             "outcome": (a.get("content") or {}).get("decision_outcome", ""), "context": (a.get("content") or {}).get("context", "")}
            for a in await decisions.list_(ctx)]


async def estimate(ctx: RequestContext, template: str) -> dict[str, Any]:
    """Pre-flight cost of generating one document: 0 for evidence documents, sections x per-section estimate for AI drafts."""
    dt = doc_type(template)
    if dt.mode != "ai":
        return {"template": template, "mode": dt.mode, "sections": 0, "outline": [], "cost_usd": {"expected": 0.0, "high": 0.0, "max": 0.0}}
    async with uow(ctx) as conn:
        snap = await arch.resolve_snapshot(conn, ctx)
        g = await arch.load_graph(conn, snap["id"]) if snap else {"nodes": {}, "edges": {}}
    ctx_data, _, _ = _context(g, "", snap or {"version": 0})
    return await ai_writer.estimate(ctx, dt, ctx_data)


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
    app_adrs = await _app_adrs(ctx) if template in ("decision-log", "arf", "prd", "developer-guide", "system-overview") else []
    if dt.mode == "ai":
        context = _context(g, title, snap)
        context[0]["app_adrs"] = app_adrs
        body, evidence, coverage = await ai_writer.write(ctx, dt, g, title, snap, context)
    else:
        body, evidence, coverage = render(template, g, title, snap, {"app_adrs": app_adrs})
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

"""C4 views from a snapshot graph (AT-DIAGRAM_STUDIO-001/005/007).

View keys:  context | system:<name> | system:<name>/group:<g> | container:<system>/<svc> | container:<system>/<svc>/group:more
Budget: at most 9 primary nodes; above that an overview groups elements and links to detail views. At most 2 focal
elements (open drift first, otherwise the most connected primary node).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

MAX_PRIMARY = 9
MAX_FOCAL = 2
RUNTIME_RELS = ("calls", "writes", "reads", "publishes", "consumes")
L2_RELS = (*RUNTIME_RELS, "depends-on")
GROUPS = [  # (group id, title, predicate on container node) — first match wins
    ("jobs", "Jobs & tooling", lambda n: n["attributes"].get("one_shot") or n["attributes"].get("optional")),
    ("data", "Data stores", lambda n: n["attributes"].get("subtype") in ("database", "storage")),
    ("messaging", "Messaging & cache", lambda n: n["attributes"].get("subtype") in ("cache", "queue")),
    ("identity", "Identity & policy", lambda n: n["attributes"].get("subtype") in ("identity", "policy")),
    ("platform", "AI & workflow platform", lambda n: n["attributes"].get("subtype") in ("gateway", "workflow")),
    ("observability", "Observability", lambda n: n["attributes"].get("subtype") == "observability"),
    ("app", "Application", lambda n: True),
]


def _system_of(g: dict[str, Any]) -> dict[str, str]:
    m = {}
    for e in g["edges"].values():
        if e["kind"] == "contains" and e["source"].startswith("system:"):
            m[e["target"]] = e["source"]
    return m


def _children(g: dict[str, Any], key: str, kind: str) -> list[str]:
    return sorted(e["target"] for e in g["edges"].values() if e["kind"] == "contains" and e["source"] == key
                  and g["nodes"].get(e["target"], {}).get("kind") == kind)


def _node_out(n: dict[str, Any], *, vkind: str, primary: bool = True, zoom: str | None = None, extra: dict | None = None) -> dict[str, Any]:
    a = n.get("attributes", {})
    return {"id": n["key"], "kind": vkind, "name": n.get("name") or n["key"], "element_kind": n.get("kind"),
            "technology": a.get("technology") or a.get("engine") or a.get("language") or "", "subtype": a.get("subtype", ""),
            "description": a.get("description", ""), "owner": a.get("owner", ""), "origins": n.get("origins", []),
            "confidence": n.get("confidence", 1), "inferred_only": n.get("inferred_only", False), "primary": primary,
            "zoom": zoom, "evidence_count": len(n.get("evidence", [])),
            "state": "completed" if a.get("one_shot_exited_ok") else a.get("state", ""), "focal": False, **(extra or {})}


def _edge_out(eid: str, src: str, dst: str, edges: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = sorted({e["kind"] for e in edges})
    protos = sorted({str(e["attributes"].get("protocol")) for e in edges if e["attributes"].get("protocol")})
    kind = next((k for k in ("writes", "publishes", "consumes", "calls", "reads", "depends-on") if k in kinds), kinds[0])
    topics = sorted({str(e["attributes"]["via_topic"]) for e in edges if e["kind"] == kind and e["attributes"].get("via_topic")})
    if topics:      # messaging rolled up from topics hosted by the broker: name the topic, not the transport
        label = f"{kind} · {topics[0]}" + (f" +{len(topics) - 1}" if len(topics) > 1 else "")
    else:
        label = (kind if kind != "depends-on" else "depends on") + (f" · {protos[0]}" if protos and protos[0] not in ("library", "in-process") else "")
    return {"id": eid, "source": src, "target": dst, "kind": kind, "kinds": kinds, "label": label, "protocols": protos,
            "count": len(edges), "origins": sorted({o for e in edges for o in e.get("origins", [])}),
            "confidence": max(float(e.get("confidence", 1)) for e in edges),
            "inferred_only": all(e.get("inferred_only") for e in edges), "members": [e["key"] for e in edges][:20], "focal": False}


def _aggregate(raw: list[tuple[str, str, dict[str, Any]]]) -> list[dict[str, Any]]:
    by: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for s, t, e in raw:
        if s != t:
            by[(s, t)].append(e)
    out = []
    for (s, t), es in sorted(by.items()):
        real = [e for e in es if e["kind"] != "depends-on"]
        out.append(_edge_out(f"{s}->{t}", s, t, real or es))
    return out


def _focal(nodes: list[dict], edges: list[dict], drift_keys: set[str]) -> None:
    picked = 0
    for coll in (edges, nodes):
        for x in coll:
            members = set(x.get("members", [])) | {x["id"]} | set(x.get("member_keys", []))
            if picked < MAX_FOCAL and members & drift_keys:
                x["focal"], x["focal_reason"] = True, "drift"
                picked += 1
    if picked == 0:
        deg: dict[str, int] = defaultdict(int)
        for e in edges:
            deg[e["source"]] += 1
            deg[e["target"]] += 1
        prim = [n for n in nodes if n["primary"] and n["kind"] not in ("person", "external", "group")]
        if prim:
            top = max(prim, key=lambda n: (deg[n["id"]], n["id"]))
            top["focal"], top["focal_reason"] = True, "most connected"


def context_view(g: dict[str, Any], drift_keys: set[str]) -> dict[str, Any]:
    sysof = _system_of(g)
    systems = sorted(k for k, n in g["nodes"].items() if n["kind"] == "software-system" and _children(g, k, "container"))
    ext = sorted(k for k, n in g["nodes"].items() if n["kind"] in ("external-system", "person"))
    nodes = [_node_out(g["nodes"][s], vkind="system", zoom=f"system:{g['nodes'][s]['name']}",
                       extra={"children": len(_children(g, s, "container"))}) for s in systems]
    nodes += [_node_out(g["nodes"][k], vkind="person" if g["nodes"][k]["kind"] == "person" else "external", primary=False) for k in ext]
    raw = []
    for e in g["edges"].values():
        if e["kind"] not in RUNTIME_RELS:
            continue
        s, t = sysof.get(e["source"], e["source"]), sysof.get(e["target"], e["target"])
        if s in systems + ext and t in systems + ext:
            raw.append((s, t, e))
    edges = _aggregate(raw)
    _focal(nodes, edges, drift_keys)
    return {"view_key": "context", "level": 1, "title": "System context", "breadcrumbs": [{"key": "context", "title": "Context"}],
            "nodes": nodes, "edges": edges, "groups": [], "detail_views": [],
            "budget": {"primary": len(systems), "max": MAX_PRIMARY, "split": False}}


HOSTED_KINDS = ("kafka-topic", "consumer-group", "event-schema", "database", "table")


def _hosts(g: dict[str, Any]) -> dict[str, str]:
    """Element -> container that hosts it (topic -> broker, table -> database server), from `contains` evidence."""
    h = {}
    for e in g["edges"].values():
        if e["kind"] == "contains" and g["nodes"].get(e["source"], {}).get("kind") == "container" \
                and g["nodes"].get(e["target"], {}).get("kind") in HOSTED_KINDS:
            h[e["target"]] = e["source"]
    for _ in range(2):                      # table -> database -> container
        for k, v in list(h.items()):
            if v in h:
                h[k] = h[v]
    return h


def _rollup(e: dict[str, Any], hosts: dict[str, str]) -> dict[str, Any]:
    """container -publishes-> topic becomes container -publishes-> broker (topic kept as `via_topic` for the label)."""
    s, t = hosts.get(e["source"], e["source"]), hosts.get(e["target"], e["target"])
    if (s, t) == (e["source"], e["target"]):
        return e
    via = e["target"] if t != e["target"] else e["source"]
    topic = via.rsplit("/", 1)[-1] if via.startswith("kafka-topic:") else ""
    return {**e, "source": s, "target": t, "attributes": {**e.get("attributes", {}), **({"via_topic": topic} if topic else {})}}


def _group_of(n: dict[str, Any]) -> tuple[str, str]:
    for gid, title, pred in GROUPS:
        if pred(n):
            return gid, title
    return "app", "Application"


def system_view(g: dict[str, Any], system: str, drift_keys: set[str], group: str | None = None, full: bool = False,
                deps: bool = False, min_conf: float = 0.5) -> dict[str, Any]:
    skey = f"system:{system}"
    if skey not in g["nodes"]:
        raise KeyError(skey)
    containers = _children(g, skey, "container")
    cset = set(containers)
    crumbs = [{"key": "context", "title": "Context"}, {"key": f"system:{system}", "title": system}]
    groups: dict[str, dict[str, Any]] = {}
    member_group: dict[str, str] = {}
    for c in containers:
        gid, title = _group_of(g["nodes"][c])
        groups.setdefault(gid, {"id": f"group:{gid}", "title": title, "members": []})["members"].append(c)
        member_group[c] = gid
    split = len(containers) > MAX_PRIMARY and not full
    neighbours: set[str] = set()
    raw = []
    rels = L2_RELS if deps else RUNTIME_RELS
    hosts = _hosts(g)
    for e0 in g["edges"].values():
        if e0["kind"] not in rels or float(e0.get("confidence", 1)) < min_conf:
            continue
        e = _rollup(e0, hosts)
        s_in, t_in = e["source"] in cset, e["target"] in cset
        if not (s_in or t_in):
            continue
        other = e["target"] if s_in else e["source"]
        if g["nodes"].get(other, {}).get("kind") not in ("container", "external-system", "person", "software-system"):
            continue                       # libraries, endpoints, components live at other levels
        s, t = e["source"], e["target"]
        if group:   # detail view: members of the group are primary, everything they touch is secondary
            if not ((s_in and member_group.get(s) == group) or (t_in and member_group.get(t) == group)):
                continue
        elif split:
            s = f"group:{member_group[s]}" if s_in else s
            t = f"group:{member_group[t]}" if t_in else t
        for x, inside in ((e["source"], s_in), (e["target"], t_in)):
            if not inside or (group and member_group.get(x) != group):
                neighbours.add(x)
        raw.append((s, t, e))
    nodes = []
    if group:
        gm = groups.get(group, {"members": [], "title": group})
        crumbs.append({"key": f"system:{system}/group:{group}", "title": gm["title"]})
        for c in gm["members"]:
            nodes.append(_node_out(g["nodes"][c], vkind="container", zoom=f"container:{c.split(':', 1)[1]}" if _children(g, c, "component") else None,
                                   extra={"components": len(_children(g, c, "component"))}))
    elif split:
        for gid, gr in sorted(groups.items(), key=lambda x: [k for k, *_ in GROUPS].index(x[0])):
            nodes.append({"id": gr["id"], "kind": "group", "name": gr["title"], "element_kind": "group", "technology": f"{len(gr['members'])} containers",
                          "primary": True, "zoom": f"system:{system}/group:{gid}", "member_keys": gr["members"], "origins": [],
                          "confidence": 1, "inferred_only": False, "evidence_count": 0, "focal": False, "subtype": "group",
                          "description": ", ".join(g["nodes"][m]["name"] for m in gr["members"])})
    else:
        for c in containers:
            nodes.append(_node_out(g["nodes"][c], vkind="container", zoom=f"container:{c.split(':', 1)[1]}" if _children(g, c, "component") else None,
                                   extra={"components": len(_children(g, c, "component")), "group": member_group[c]}))
    for k in sorted(neighbours - {n["id"] for n in nodes}):
        if k in g["nodes"] and not (split and not group and k in cset):
            n = g["nodes"][k]
            vk = "person" if n["kind"] == "person" else "external" if n["kind"] == "external-system" else "container"
            nodes.append(_node_out(n, vkind=vk, primary=False))
    ids = {n["id"] for n in nodes}
    edges = [e for e in _aggregate(raw) if e["source"] in ids and e["target"] in ids]
    _focal(nodes, edges, drift_keys)
    vk = f"system:{system}" + (f"/group:{group}" if group else "")
    return {"view_key": vk, "level": 2, "title": f"{system} — containers" + (f" · {groups[group]['title']}" if group and group in groups else ""),
            "breadcrumbs": crumbs, "nodes": nodes, "edges": edges,
            "groups": [{"id": gr["id"], "title": gr["title"], "members": gr["members"]} for gr in groups.values()],
            "detail_views": [{"key": f"system:{system}/group:{gid}", "title": gr["title"], "count": len(gr["members"])}
                             for gid, gr in groups.items()] if split else [],
            "budget": {"primary": len([n for n in nodes if n["primary"]]), "max": MAX_PRIMARY, "split": split,
                       "containers": len(containers)}}


def container_view(g: dict[str, Any], ckey: str, drift_keys: set[str], group: str | None = None) -> dict[str, Any]:
    if ckey not in g["nodes"]:
        raise KeyError(ckey)
    system, svc = ckey.split(":", 1)[1].split("/", 1)
    comps = _children(g, ckey, "component")
    crumbs = [{"key": "context", "title": "Context"}, {"key": f"system:{system}", "title": system},
              {"key": f"container:{system}/{svc}", "title": svc}]
    base = {"view_key": f"container:{system}/{svc}" + (f"/group:{group}" if group else ""), "level": 3,
            "title": f"{svc} — components", "breadcrumbs": crumbs, "groups": [], "detail_views": []}
    if not comps:
        return {**base, "nodes": [], "edges": [], "empty_reason": "No component-level evidence exists for this container.",
                "budget": {"primary": 0, "max": MAX_PRIMARY, "split": False}}
    cset = set(comps)
    deg: dict[str, int] = defaultdict(int)
    internal = [e for e in g["edges"].values() if e["kind"] == "depends-on" and e["source"] in cset and e["target"] in cset]
    for e in internal:
        deg[e["source"]] += 1
        deg[e["target"]] += 1
    ranked = sorted(comps, key=lambda c: (-deg[c], c))
    split = len(comps) > MAX_PRIMARY
    page = int(group[4:] or 1) if group and group.startswith("more") else 0
    window = ranked[(MAX_PRIMARY - 1) * page:] if page else ranked
    if len(window) > MAX_PRIMARY:
        keep, rest = set(window[:MAX_PRIMARY - 1]), window[MAX_PRIMARY - 1:]
    else:
        keep, rest = set(window), []
    more_id = f"more{page + 1}" if page else "more"
    if page:
        crumbs.append({"key": base["view_key"], "title": f"Supporting modules {page}" if page > 1 else "Supporting modules"})
    nodes = [_node_out(g["nodes"][c], vkind="component", zoom=c if _children(g, c, "code") else None) for c in sorted(keep)]
    if rest:
        nodes.append({"id": "group:more", "kind": "group", "name": "Supporting modules", "technology": f"{len(rest)} components",
                      "primary": True, "zoom": f"container:{system}/{svc}/group:{more_id}", "member_keys": rest, "origins": [], "confidence": 1,
                      "inferred_only": False, "evidence_count": 0, "focal": False, "subtype": "group", "element_kind": "group",
                      "description": ", ".join(g["nodes"][c]["name"] for c in rest[:12])})
    rest_set = set(rest)
    raw = []
    for e in internal:
        s = e["source"] if e["source"] in keep else ("group:more" if e["source"] in rest_set else None)
        t = e["target"] if e["target"] in keep else ("group:more" if e["target"] in rest_set else None)
        if s and t:
            raw.append((s, t, e))
    edges = _aggregate(raw)
    for e in edges:
        n = sum(int(g["edges"][m]["attributes"].get("imports", 1)) for m in e["members"] if m in g["edges"])
        e["label"], e["kind"], e["imports"] = f"imports ×{n}", "imports", n
    hidden = 0
    if len(edges) > 20:                 # declutter: hide single-import edges, but say so (never silently)
        strong = [e for e in edges if e["imports"] > 1]
        hidden = len(edges) - len(strong)
        edges = strong
    _focal(nodes, edges, drift_keys)
    return {**base, "breadcrumbs": crumbs, "nodes": nodes, "edges": edges,
            "detail_views": [{"key": f"container:{system}/{svc}/group:{more_id}", "title": "Supporting modules", "count": len(rest)}] if rest else [],
            "budget": {"primary": len(nodes), "max": MAX_PRIMARY, "split": split, "components": len(comps)},
            "hidden_edges": hidden, "hidden_reason": "single-import dependencies hidden for readability" if hidden else ""}


def code_view(g: dict[str, Any], comp_key: str, drift_keys: set[str], group: str | None = None) -> dict[str, Any]:
    """C4 L4 (code): the classes and functions of one component, their inheritance and `uses` references, and the code they
    depend on in other components (secondary, zoomable). Same 9-primary budget with a paged "more" group."""
    if comp_key not in g["nodes"]:
        raise KeyError(comp_key)
    system, svc, comp = comp_key.split(":", 1)[1].split("/", 2)
    cname = g["nodes"][comp_key].get("name", comp)
    crumbs = [{"key": "context", "title": "Context"}, {"key": f"system:{system}", "title": system},
              {"key": f"container:{system}/{svc}", "title": svc}, {"key": comp_key, "title": cname}]
    base = {"view_key": comp_key + (f"/group:{group}" if group else ""), "level": 4, "title": f"{cname} — code", "breadcrumbs": crumbs,
            "groups": [], "detail_views": []}
    code = _children(g, comp_key, "code")
    if not code:
        return {**base, "nodes": [], "edges": [], "empty_reason": "No code-level evidence (classes/functions) for this component.",
                "budget": {"primary": 0, "max": MAX_PRIMARY, "split": False}}
    cset = set(code)
    deps = [e for e in g["edges"].values() if e["kind"] == "depends-on" and (e["source"] in cset or e["target"] in cset)
            and g["nodes"].get(e["source"], {}).get("kind") == "code" and g["nodes"].get(e["target"], {}).get("kind") == "code"]
    deg: dict[str, int] = defaultdict(int)
    for e in deps:
        deg[e["source"]] += 1
        deg[e["target"]] += 1
    ranked = sorted(code, key=lambda c: (-deg[c], g["nodes"][c]["attributes"].get("element") != "class", c))
    page = int(group[4:] or 1) if group and group.startswith("more") else 0
    window = ranked[(MAX_PRIMARY - 1) * page:] if page else ranked
    keep, rest = (set(window[:MAX_PRIMARY - 1]), window[MAX_PRIMARY - 1:]) if len(window) > MAX_PRIMARY else (set(window), [])
    more_id = f"more{page + 1}" if page else "more"
    if page:
        crumbs.append({"key": base["view_key"], "title": f"More code {page}"})
    owner: dict[str, str] = {}
    for e in g["edges"].values():
        if e["kind"] == "contains" and g["nodes"].get(e["target"], {}).get("kind") == "code":
            owner[e["target"]] = e["source"]
    nodes = []
    for c in sorted(keep):
        n = g["nodes"][c]
        a = n["attributes"]
        out = _node_out(n, vkind="component")
        out["subtype"] = a.get("element", "code")
        out["technology"] = f"{a.get('element', 'code')} · {a.get('path', '')}:{a.get('line_start', '')}"
        out["description"] = (f"bases: {', '.join(a.get('bases') or [])}" if a.get("bases") else "") + (f" · {a['methods']} methods" if a.get("methods") else "")
        nodes.append(out)
    if rest:
        nodes.append({"id": "group:more", "kind": "group", "name": "More code", "technology": f"{len(rest)} elements", "primary": True,
                      "zoom": f"{comp_key}/group:{more_id}", "member_keys": rest, "origins": [], "confidence": 1, "inferred_only": False,
                      "evidence_count": 0, "focal": False, "subtype": "group", "element_kind": "group",
                      "description": ", ".join(g["nodes"][c]["name"] for c in rest[:12])})
    rest_set = set(rest)
    external: dict[str, int] = defaultdict(int)
    raw = []
    for e in deps:
        def place(k: str) -> str | None:
            if k in keep:
                return k
            if k in rest_set:
                return "group:more"
            if k not in cset:
                external[k] += 1
                return k
            return None
        s_, t_ = place(e["source"]), place(e["target"])
        if s_ and t_:
            raw.append((s_, t_, e))
    ext_keep = {k for k, _ in sorted(external.items(), key=lambda x: -x[1])[:5]}
    for k in sorted(ext_keep):
        n = g["nodes"][k]
        nodes.append({**_node_out(n, vkind="external", primary=False, zoom=owner.get(k)),
                      "technology": f"{g['nodes'].get(owner.get(k, ''), {}).get('name', 'other component')} · {n['attributes'].get('element', '')}"})
    raw = [(s_, t_, e) for s_, t_, e in raw if (s_ in keep or s_ == "group:more" or s_ in ext_keep) and (t_ in keep or t_ == "group:more" or t_ in ext_keep)]
    edges = _aggregate(raw)
    for e in edges:
        rels = sorted({g["edges"][m]["attributes"].get("relation", "uses") for m in e["members"] if m in g["edges"]})
        e["kind"], e["label"] = ("inherits", "inherits") if rels == ["inherits"] else ("uses", " / ".join(rels))
    _focal(nodes, edges, drift_keys)
    return {**base, "breadcrumbs": crumbs, "nodes": nodes, "edges": edges,
            "detail_views": [{"key": f"{comp_key}/group:{more_id}", "title": "More code", "count": len(rest)}] if rest else [],
            "budget": {"primary": len([n for n in nodes if n.get("primary")]), "max": MAX_PRIMARY, "split": bool(rest), "code_elements": len(code)}}


VKIND = {"software-system": "system", "external-system": "external", "person": "person", "container": "container", "component": "component",
         "code": "component", "database": "container", "table": "component", "kafka-topic": "container", "api-endpoint": "component",
         "adr": "component", "work-item": "component"}


def zoom_target(g: dict[str, Any], k: str) -> str | None:
    """The view that shows what is inside element `k` (C4 zoom), or None."""
    n = g["nodes"].get(k, {})
    if n.get("kind") == "software-system":
        return f"system:{k.split(':', 1)[1]}"
    if n.get("kind") == "container" and _children(g, k, "component"):
        return k
    if n.get("kind") == "component" and _children(g, k, "code"):
        return k
    return None


def parent_view(g: dict[str, Any], k: str) -> str:
    """The view in which element `k` itself is drawn (for "open in Architecture" / search)."""
    kind = g["nodes"].get(k, {}).get("kind")
    for e in g["edges"].values():
        if e["kind"] == "contains" and e["target"] == k:
            pk = g["nodes"].get(e["source"], {}).get("kind")
            if pk == "software-system":
                return f"system:{e['source'].split(':', 1)[1]}"
            if pk in ("container", "component"):
                return e["source"]
    if kind == "table" or kind == "code":
        for e in g["edges"].values():
            if e["target"] == k and g["nodes"].get(e["source"], {}).get("kind") in ("container", "component"):
                return e["source"]
    return "context"


def evidence_view(g: dict[str, Any], keys: list[str], max_nodes: int = 14) -> dict[str, Any] | None:
    """A diagram for an assistant answer: the cited elements, the endpoints of cited relationships and the direct relations
    among them; every node zooms into its C4 level (L1-L4) in the Architecture tab."""
    want: list[str] = []
    for k in keys:
        if k in g["edges"]:
            e = g["edges"][k]
            for x in (e["source"], e["target"]):
                if x not in want:
                    want.append(x)
        elif k in g["nodes"] and k not in want:
            want.append(k)
    want = [k for k in want if g["nodes"].get(k, {}).get("kind") not in ("library", "document")][:max_nodes]
    if len(want) < 2:
        return None
    ws = set(want)
    nodes = []
    for k in want:
        n = g["nodes"][k]
        out = _node_out(n, vkind=VKIND.get(n["kind"], "container"), zoom=zoom_target(g, k))
        out["parent_view"] = parent_view(g, k)
        if n["kind"] == "table":
            out["technology"] = f"table · {n['attributes'].get('column_count', '?')} columns"
        nodes.append(out)
    raw = [(e["source"], e["target"], e) for e in g["edges"].values()
           if e["source"] in ws and e["target"] in ws and e["kind"] not in ("contains",)]
    edges = _aggregate(raw)
    return {"view_key": "answer", "level": 0, "title": "Diagram for this answer", "breadcrumbs": [], "nodes": nodes, "edges": edges,
            "detail_views": [], "budget": {"primary": len(nodes), "max": max_nodes, "split": False}, "layout": {"overrides": {}, "revision": 0}}


def annotate_links(g: dict[str, Any], view: dict[str, Any]) -> dict[str, Any]:
    """Per node: how many ADRs, work items (Taiga/GitLab/GitHub) and documented diagram relations point at it or at an
    element it contains — so docs and plans show up on the diagram, not only code."""
    contains: dict[str, list[str]] = defaultdict(list)
    for e in g["edges"].values():
        if e["kind"] == "contains":
            contains[e["source"]].append(e["target"])
    refs: dict[str, dict[str, int]] = defaultdict(lambda: {"adrs": 0, "work_items": 0, "documented": 0})
    for e in g["edges"].values():
        src_kind = g["nodes"].get(e["source"], {}).get("kind")
        if e["kind"] == "references" and src_kind in ("adr", "work-item"):
            refs[e["target"]]["adrs" if src_kind == "adr" else "work_items"] += 1
        if e["attributes"].get("documented"):
            refs[e["source"]]["documented"] += 1
            refs[e["target"]]["documented"] += 1

    def total(k: str, depth: int = 0) -> dict[str, int]:
        t = dict(refs.get(k, {"adrs": 0, "work_items": 0, "documented": 0}))
        if depth < 3:
            for c in contains.get(k, []):
                for a, v in total(c, depth + 1).items():
                    t[a] += v
        return t
    for n in view.get("nodes", []):
        n["links"] = total(n["id"]) if n.get("kind") != "group" else {"adrs": 0, "work_items": 0, "documented": 0}
    return view


def build_view(g: dict[str, Any], view_key: str, drift_keys: set[str] | None = None, full: bool = False, deps: bool = False,
               min_conf: float = 0.5) -> dict[str, Any]:
    return annotate_links(g, _build_view(g, view_key, drift_keys, full, deps, min_conf))


def _build_view(g: dict[str, Any], view_key: str, drift_keys: set[str] | None = None, full: bool = False, deps: bool = False,
                min_conf: float = 0.5) -> dict[str, Any]:
    drift_keys = drift_keys or set()
    if view_key == "context":
        return context_view(g, drift_keys)
    if view_key.startswith("system:"):
        rest = view_key[len("system:"):]
        system, _, grp = rest.partition("/group:")
        v = system_view(g, system, drift_keys, grp or None, full, deps, min_conf)
        v["options"] = {"full": full, "deps": deps, "min_conf": min_conf}
        return v
    if view_key.startswith("component:"):
        comp, _, grp = view_key.partition("/group:")
        return code_view(g, comp, drift_keys, grp or None)
    if view_key.startswith("container:"):
        rest = view_key[len("container:"):]
        base, _, grp = rest.partition("/group:")
        return container_view(g, f"container:{base}", drift_keys, grp or None)
    raise KeyError(view_key)

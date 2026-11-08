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
GROUPS = [  # (group id, title, predicate on container node)
    ("data", "Data stores", lambda n: n["attributes"].get("subtype") in ("database", "storage")),
    ("messaging", "Messaging & cache", lambda n: n["attributes"].get("subtype") in ("cache", "queue")),
    ("identity", "Identity & policy", lambda n: n["attributes"].get("subtype") in ("identity", "policy")),
    ("platform", "AI & workflow platform", lambda n: n["attributes"].get("subtype") in ("gateway", "workflow")),
    ("observability", "Observability", lambda n: n["attributes"].get("subtype") == "observability"),
    ("jobs", "Jobs & tooling", lambda n: n["attributes"].get("one_shot") or n["attributes"].get("optional")),
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
            "zoom": zoom, "evidence_count": len(n.get("evidence", [])), "state": a.get("state", ""), "focal": False, **(extra or {})}


def _edge_out(eid: str, src: str, dst: str, edges: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = sorted({e["kind"] for e in edges})
    protos = sorted({str(e["attributes"].get("protocol")) for e in edges if e["attributes"].get("protocol")})
    kind = next((k for k in ("writes", "calls", "reads", "publishes", "consumes", "depends-on") if k in kinds), kinds[0])
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
    for e in g["edges"].values():
        if e["kind"] not in rels or float(e.get("confidence", 1)) < min_conf:
            continue
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
    nodes = [_node_out(g["nodes"][c], vkind="component") for c in sorted(keep)]
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


def build_view(g: dict[str, Any], view_key: str, drift_keys: set[str] | None = None, full: bool = False, deps: bool = False,
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
    if view_key.startswith("container:"):
        rest = view_key[len("container:"):]
        base, _, grp = rest.partition("/group:")
        return container_view(g, f"container:{base}", drift_keys, grp or None)
    raise KeyError(view_key)

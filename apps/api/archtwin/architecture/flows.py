"""Automatically recognized flows (Flows tab) — deterministic, from the snapshot graph of ALL datasources.

* request flows: from each entry point (a person, or a container nobody calls that serves HTTP / runs on a schedule /
  consumes events) along runtime relations (calls, reads, writes, publishes), depth-first, cycles cut, at most MAX_STEPS;
  cross-repository and cross-system hops are included (resolved names), so distributed flows appear end to end.
* event flows: for each topic, producers -> topic -> consumers -> what each consumer does next (one hop).
* endpoint flows: for each HTTP endpoint, the caller (user, web UI or another service) -> the handler component -> the
  components its route module uses -> the resources they touch (databases, SaaS APIs, ML runtime, tools, volumes).
* data flows: for each database, who writes and who reads.
Every step carries its relation, protocol, origins, confidence and evidence count; a flow is `documented` when a step comes
only from a diagram in the docs, and `inferred` when any step is inferred only. Nothing is invented: no edge, no step.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any

RUNTIME = ("calls", "writes", "reads", "publishes", "consumes")
ACTORS = ("container", "software-system", "external-system", "person", "database", "kafka-topic", "service")
MAX_STEPS = 14
MAX_FLOWS = 250
MAX_ENDPOINT_FLOWS = 150
RESOURCE_KINDS = ("external-system", "database", "kafka-topic")


def _fid(kind: str, key: str) -> str:
    return f"{kind}-" + hashlib.sha1(key.encode()).hexdigest()[:10]


def _step(g: dict[str, Any], e: dict[str, Any], src: str | None = None, dst: str | None = None) -> dict[str, Any]:
    a = e["attributes"]
    return {"from": src or e["source"], "to": dst or e["target"], "kind": e["kind"], "edge": e["key"],
            "label": a.get("label") or a.get("via_topic") or a.get("protocol") or e["kind"], "protocol": a.get("protocol", ""),
            "origins": e.get("origins", []), "confidence": e.get("confidence", 1), "inferred_only": e.get("inferred_only", False),
            "documented": bool(a.get("documented")), "evidence": len(e.get("evidence", []))}


def _participant(g: dict[str, Any], k: str, system_of: dict[str, str]) -> dict[str, Any]:
    n = g["nodes"].get(k, {})
    a = n.get("attributes", {})
    return {"key": k, "name": n.get("name", k), "kind": n.get("kind", ""), "subtype": a.get("subtype", ""),
            "system": system_of.get(k, k if k.startswith("system:") else ""), "technology": a.get("technology", "")}


def _finish(g: dict[str, Any], fid: str, kind: str, name: str, steps: list[dict[str, Any]], system_of: dict[str, str],
            entry: str | None = None) -> dict[str, Any]:
    order: list[str] = []
    for s in steps:
        for k in (s["from"], s["to"]):
            if k not in order:
                order.append(k)
    systems = sorted({system_of.get(k, "") for k in order if system_of.get(k)})
    return {"id": fid, "kind": kind, "name": name, "entry": entry, "steps": steps, "participants": [_participant(g, k, system_of) for k in order],
            "systems": systems, "distributed": len(systems) > 1, "confidence": round(min((s["confidence"] for s in steps), default=1), 3),
            "inferred": any(s["inferred_only"] for s in steps), "documented": any(s["documented"] for s in steps), "length": len(steps)}


def recognize(g: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = g["nodes"], g["edges"]
    system_of: dict[str, str] = {}
    for e in edges.values():
        if e["kind"] == "contains" and e["source"].startswith("system:"):
            system_of[e["target"]] = e["source"].split(":", 1)[1]
    out_e: dict[str, list[dict[str, Any]]] = defaultdict(list)
    in_deg: dict[str, int] = defaultdict(int)
    for e in edges.values():
        if e["kind"] in RUNTIME and nodes.get(e["source"], {}).get("kind") in ACTORS and nodes.get(e["target"], {}).get("kind") in ACTORS:
            out_e[e["source"]].append(e)
            if nodes[e["source"]]["kind"] != "person":
                in_deg[e["target"]] += 1
    for es in out_e.values():
        es.sort(key=lambda e: (e["kind"] not in ("calls",), -e.get("confidence", 1), e["target"]))
    exposes = {e["source"] for e in edges.values() if e["kind"] == "exposes"}
    flows: list[dict[str, Any]] = []

    # ---- request flows from entry points
    entries = [k for k, n in nodes.items() if n["kind"] == "person" and out_e.get(k)]
    entries += sorted(k for k, n in nodes.items() if n["kind"] == "container" and out_e.get(k) and not in_deg.get(k)
                      and (k in exposes or n["attributes"].get("subtype") in ("webapp", "gateway", "worker", "scheduler", "service")
                           or any(e["kind"] == "consumes" for e in out_e[k])))
    for start in entries:
        steps: list[dict[str, Any]] = []
        visited = {start}

        def dfs(k: str, depth: int, steps: list[dict[str, Any]] = steps, visited: set[str] = visited) -> None:
            for e in out_e.get(k, []):
                if len(steps) >= MAX_STEPS or depth > 6:
                    return
                if e["kind"] == "consumes":         # a consumer reads FROM the topic: the arrow is topic -> consumer
                    continue
                steps.append(_step(g, e))
                if e["target"] not in visited:
                    visited.add(e["target"])
                    if nodes.get(e["target"], {}).get("kind") not in ("database", "external-system"):
                        dfs(e["target"], depth + 1)
        dfs(start, 0)
        if len(steps) >= 1 and not (len(steps) == 1 and nodes[start]["kind"] == "person"):
            first = nodes[start]
            name = f"{first.get('name', start)} request flow" if first["kind"] != "person" else \
                f"{first.get('name', 'User')} → {nodes.get(steps[0]['to'], {}).get('name', '')}"
            flows.append(_finish(g, _fid("request", start), "request", name, steps, system_of, entry=start))

    flows += _endpoint_flows(g, system_of)

    # ---- event flows per topic
    for k, n in sorted(nodes.items()):
        if n["kind"] != "kafka-topic":
            continue
        prod = [e for e in edges.values() if e["kind"] == "publishes" and e["target"] == k]
        cons = [e for e in edges.values() if e["kind"] == "consumes" and e["target"] == k]
        if not prod and not cons:
            continue
        steps = [_step(g, e) for e in prod]
        for e in cons:
            steps.append(_step(g, e, src=k, dst=e["source"]))             # topic delivers to the consumer
            for nxt in out_e.get(e["source"], [])[:3]:
                if nxt["kind"] != "consumes":
                    steps.append(_step(g, nxt))
        flows.append(_finish(g, _fid("event", k), "event", f"Event: {n.get('name', k)}", steps[:MAX_STEPS], system_of, entry=k))

    # ---- data flows per database
    for k, n in sorted(nodes.items()):
        if not (n["kind"] == "database" or (n["kind"] == "container" and n["attributes"].get("subtype") in ("database", "storage"))):
            continue
        io = sorted((e for e in edges.values() if e["target"] == k and e["kind"] in ("writes", "reads")), key=lambda e: (e["kind"] != "writes", e["source"]))
        if not io:
            continue
        flows.append(_finish(g, _fid("data", k), "data", f"Data: {n.get('name', k)}", [_step(g, e) for e in io[:MAX_STEPS]], system_of, entry=k))

    flows.sort(key=lambda f: ({"request": 0, "endpoint": 1, "event": 2, "data": 3}[f["kind"]], -f["length"], f["name"]))
    return {"flows": flows[:MAX_FLOWS], "total": len(flows),
            "counts": {k: sum(1 for f in flows if f["kind"] == k) for k in ("request", "endpoint", "event", "data")}}


def _is_resource(g: dict[str, Any], k: str) -> bool:
    n = g["nodes"].get(k, {})
    return n.get("kind") in RESOURCE_KINDS or n.get("attributes", {}).get("subtype") in ("storage", "ml", "database", "cache", "queue")


def _synthetic(src: str, dst: str, kind: str, label: str, confidence: float = 1.0, origins: list[str] | None = None) -> dict[str, Any]:
    """A step implied by the endpoint's own evidence (route module imports), not by a single graph edge."""
    return {"from": src, "to": dst, "kind": kind, "edge": f"{src}|{kind}|{dst}", "label": label, "protocol": "in-process" if kind == "uses" else "",
            "origins": origins or ["static"], "confidence": confidence, "inferred_only": False, "documented": False, "evidence": 1}


def _endpoint_flows(g: dict[str, Any], system_of: dict[str, str]) -> list[dict[str, Any]]:
    nodes, edges = g["nodes"], g["edges"]
    callers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in edges.values():
        if e["kind"] == "calls" and nodes.get(e["target"], {}).get("kind") == "api-endpoint":
            callers[e["target"]].append(e)
    entry_of: dict[str, list[dict[str, Any]]] = defaultdict(list)          # who reaches a UI component (the user)
    for e in edges.values():
        if e["kind"] == "calls" and nodes.get(e["source"], {}).get("kind") == "person":
            entry_of[e["target"]].append(e)
    comp_out: dict[str, list[dict[str, Any]]] = defaultdict(list)       # component -> runtime relations to resources
    for e in edges.values():
        if e["kind"] in RUNTIME and nodes.get(e["source"], {}).get("kind") == "component" and _is_resource(g, e["target"]):
            comp_out[e["source"]].append(e)
    for es in comp_out.values():
        es.sort(key=lambda e: (-e.get("confidence", 1), e["target"]))
    flows = []
    eps = sorted((k for k, n in nodes.items() if n["kind"] == "api-endpoint" and n["attributes"].get("component") in nodes),
                 key=lambda k: (nodes[k]["attributes"].get("path", ""), nodes[k]["attributes"].get("method", "")))
    for ek in eps[:MAX_ENDPOINT_FLOWS]:
        a = nodes[ek]["attributes"]
        handler = a["component"]
        label = f"{a.get('method', '')} {a.get('path', '')}".strip()
        steps: list[dict[str, Any]] = []
        for c in callers.get(ek, [])[:1]:
            for pe in entry_of.get(c["source"], [])[:1]:
                steps.append(_step(g, pe))
            steps.append({**_step(g, c, src=c["source"], dst=handler), "label": label, "kind": "calls"})
        if not steps:
            steps.append(_synthetic(ek, handler, "handles", label))
        for comp in a.get("uses", [])[:6]:
            if comp in nodes:
                steps.append(_synthetic(handler, comp, "uses", "imports"))
                steps += [_step(g, e) for e in comp_out.get(comp, [])[:4]]
        for r in a.get("resources", [])[:4]:
            if r in nodes:
                steps.append(_synthetic(handler, r, "calls", r.split(":")[-1], 0.85))
        if len(steps) >= 2:
            f = _finish(g, _fid("endpoint", ek), "endpoint", label, steps[:MAX_STEPS], system_of, entry=ek)
            f["endpoint"] = ek
            flows.append(f)
    return flows

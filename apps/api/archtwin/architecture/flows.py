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
ACTORS = ("container", "software-system", "external-system", "person", "database", "kafka-topic", "service", "workflow", "message-channel")
CHANNEL_KINDS = ("kafka-topic", "workflow", "message-channel")
MAX_STEPS = 14
MAX_FLOWS = 800
MAX_ENDPOINT_FLOWS = 600
RESOURCE_KINDS = ("external-system", "database", "kafka-topic", "workflow", "message-channel")


def _systems(g: dict[str, Any]) -> dict[str, str]:
    """Every element -> the software system it belongs to (climbing contains/exposes; key prefix as a fallback)."""
    parent: dict[str, str] = {}
    for e in g["edges"].values():
        if e["kind"] in ("contains", "exposes") and e["target"] not in parent:
            parent[e["target"]] = e["source"]
    out: dict[str, str] = {}
    for k in g["nodes"]:
        cur, hops = k, 0
        while cur in parent and not cur.startswith("system:") and hops < 6:
            cur, hops = parent[cur], hops + 1
        if cur.startswith("system:"):
            out[k] = cur.split(":", 1)[1]
        elif k.split(":", 1)[0] in ("container", "component", "endpoint", "code", "table", "database") and "/" in k:
            out[k] = k.split(":", 1)[1].split("/", 1)[0]
    return out


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
    seen_steps: set[tuple[str, str, str, str]] = set()
    uniq = []
    for st in steps:                       # the same hop twice (container + component evidence) is one step
        sig = (st["from"], st["to"], st["kind"], st.get("label", ""))
        if sig not in seen_steps:
            seen_steps.add(sig)
            uniq.append(st)
    steps = uniq
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
    system_of = _systems(g)
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

    # ---- event flows per channel: Kafka topic, durable workflow (started -> executed -> effects), NOTIFY channel
    for k, n in sorted(nodes.items()):
        if n["kind"] not in CHANNEL_KINDS:
            continue
        if n["kind"] == "workflow":
            wf = _workflow_flow(g, k, out_e, system_of)
            if wf:
                flows.append(wf)
            continue
        if n["attributes"].get("in_process"):          # an application event inside one runtime (module -> module)
            prod = [e for e in edges.values() if e["kind"] == "publishes" and e["target"] == k]
            steps = [{**_step(g, e), "label": e["attributes"].get("label", "publishes")} for e in prod[:4]] + listener_steps(g, k, depth=2)
            if steps:
                flows.append(_finish(g, _fid("event", k), "event", f"Event: {n.get('name', k)}", steps[:MAX_STEPS], system_of, entry=k))
            continue
        prod = [e for e in edges.values() if e["kind"] == "publishes" and e["target"] == k and nodes.get(e["source"], {}).get("kind") != "component"]
        cons = [e for e in edges.values() if e["kind"] == "consumes" and e["target"] == k and nodes.get(e["source"], {}).get("kind") != "component"]
        if not prod and not cons:
            continue
        steps = [_step(g, e) for e in prod]
        for e in cons:
            steps.append(_step(g, e, src=k, dst=e["source"]))             # topic delivers to the consumer
            if n["kind"] == "message-channel":   # a NOTIFY channel ends in the endpoints that stream it to clients
                streams = [x for x, xn in nodes.items() if xn["kind"] == "api-endpoint" and k in xn["attributes"].get("listens", [])
                           and xn["attributes"].get("component", "").startswith(e["source"].replace("container:", "component:") + "/")]
                steps += [{**_synthetic(e["source"], x, "streams", nodes[x]["name"], 0.9), "protocol": "sse"} for x in streams[:3]]
                continue
            for nxt in out_e.get(e["source"], [])[:3]:
                if nxt["kind"] != "consumes":
                    steps.append(_step(g, nxt))
        title = f"Notification: {n.get('name', k)}" if n["kind"] == "message-channel" else f"Event: {n.get('name', k)}"
        flows.append(_finish(g, _fid("event", k), "event", title, steps[:MAX_STEPS], system_of, entry=k))

    # ---- data flows per database
    for k, n in sorted(nodes.items()):
        if not (n["kind"] == "database" or (n["kind"] == "container" and n["attributes"].get("subtype") in ("database", "storage"))):
            continue
        io = sorted((e for e in edges.values() if e["target"] == k and e["kind"] in ("writes", "reads")), key=lambda e: (e["kind"] != "writes", e["source"]))
        if not io:
            continue
        flows.append(_finish(g, _fid("data", k), "data", f"Data: {n.get('name', k)}", [_step(g, e) for e in io[:MAX_STEPS]], system_of, entry=k))

    # most explanatory first: entry points with their effects, then workflows/events, then generic request walks, then stores
    flows.sort(key=lambda f: ({"endpoint": 0, "event": 1, "request": 2, "data": 3}[f["kind"]], -f["length"], f["name"]))
    return {"flows": flows[:MAX_FLOWS], "total": len(flows),
            "counts": {k: sum(1 for f in flows if f["kind"] == k) for k in ("request", "endpoint", "event", "data")}}


def _is_resource(g: dict[str, Any], k: str) -> bool:
    n = g["nodes"].get(k, {})
    return n.get("kind") in RESOURCE_KINDS or n.get("attributes", {}).get("subtype") in ("storage", "ml", "database", "cache", "queue")


def _synthetic(src: str, dst: str, kind: str, label: str, confidence: float = 1.0, origins: list[str] | None = None) -> dict[str, Any]:
    """A step implied by the endpoint's own evidence (route module imports), not by a single graph edge."""
    return {"from": src, "to": dst, "kind": kind, "edge": f"{src}|{kind}|{dst}", "label": label, "protocol": "in-process" if kind == "uses" else "",
            "origins": origins or ["static"], "confidence": confidence, "inferred_only": False, "documented": False, "evidence": 1}


MAX_HOPS = 3


def _endpoint_flows(g: dict[str, Any], system_of: dict[str, str]) -> list[dict[str, Any]]:
    """User -> UI -> endpoint handler -> used components -> resources, continuing into the endpoints it calls in other
    services (gateways, BFFs, service-to-service HTTP) so distributed flows are end to end."""
    nodes, edges = g["nodes"], g["edges"]
    callers: dict[str, list[dict[str, Any]]] = defaultdict(list)       # endpoint <- who calls it
    calls: dict[str, list[dict[str, Any]]] = defaultdict(list)         # endpoint -> endpoints/services it calls
    entry_of: dict[str, list[dict[str, Any]]] = defaultdict(list)      # UI component <- the user
    owner: dict[str, str] = {}                                         # endpoint -> container exposing it
    parent: dict[str, str] = {}                                        # component -> container containing it
    comp_out: dict[str, list[dict[str, Any]]] = defaultdict(list)      # component -> resources
    for e in edges.values():
        sk, tk = nodes.get(e["source"], {}).get("kind"), nodes.get(e["target"], {}).get("kind")
        if e["kind"] == "contains" and tk == "component":
            parent[e["target"]] = e["source"]
        if e["kind"] == "exposes" and tk == "api-endpoint":
            owner[e["target"]] = e["source"]
        elif e["kind"] == "calls" and tk == "api-endpoint" and sk != "api-endpoint":
            callers[e["target"]].append(e)
        elif e["kind"] == "calls" and sk == "api-endpoint" and tk in ("api-endpoint", "container"):
            calls[e["source"]].append(e)
        elif e["kind"] == "calls" and sk == "person":
            entry_of[e["target"]].append(e)
        if e["kind"] in RUNTIME and e["kind"] != "consumes" and sk == "component" and _is_resource(g, e["target"]):
            comp_out[e["source"]].append(e)          # background LISTENs / consumers are not part of a request
    for es in comp_out.values():
        es.sort(key=lambda e: (-e.get("confidence", 1), e["target"]))
    # shared kernel: components imported by most endpoints' handlers (config, ids, logging, db helpers) explain nothing
    use_count: dict[str, int] = defaultdict(int)
    n_eps = 0
    for n in nodes.values():
        if n["kind"] == "api-endpoint" and n["attributes"].get("uses"):
            n_eps += 1
            for c in set(n["attributes"]["uses"]):
                use_count[c] += 1
    shared_kernel = {c for c, k in use_count.items() if n_eps >= 8 and k >= 0.5 * n_eps}

    def handler_of(ek: str) -> str | None:
        h = nodes[ek]["attributes"].get("component")
        return h if h in nodes else owner.get(ek)

    def trace(ek: str, hop: int, seen: set[str]) -> list[dict[str, Any]]:
        a, handler = nodes[ek]["attributes"], handler_of(ek)
        if not handler:
            return []
        steps: list[dict[str, Any]] = []
        owner_c = owner.get(ek, handler)
        if "effects" in a:          # handler-level evidence: what this route's code does (not every import of its module)
            steps += effect_steps(g, handler, a["effects"], owner_c, depth=2)
        else:
            for comp in a.get("uses", [])[:6]:
                if comp in nodes and comp not in shared_kernel:
                    steps.append(_synthetic(handler, comp, "uses", "imports"))
                    steps += [_step(g, e) for e in comp_out.get(comp, [])[:4]]
            steps += [_synthetic(handler, r, "calls", r.split(":")[-1], 0.85) for r in a.get("resources", [])[:4] if r in nodes]
        for wk in a.get("starts", [])[:3]:
            if wk in nodes:
                steps.append({**_synthetic(handler, wk, "starts", f"starts {nodes[wk]['name']}", 0.95), "protocol": "temporal"})
                steps += workflow_steps(g, wk, depth=0)
        for ck in a.get("notifies", [])[:2]:
            if ck in nodes:
                steps.append({**_synthetic(handler, ck, "publishes", f"NOTIFY {nodes[ck]['name']}", 0.9), "protocol": "postgres-notify"})
                steps += channel_delivery(g, ck)
        for ck in a.get("listens", [])[:2]:
            if ck in nodes:
                producers = [e for e in g["edges"].values() if e["kind"] == "publishes" and e["target"] == ck
                             and nodes.get(e["source"], {}).get("kind") == "container"][:3]
                steps += [_step(g, e) for e in producers]
                steps.append({**_synthetic(ck, handler, "delivers", f"LISTEN {nodes[ck]['name']} (stream)", 0.9), "protocol": "postgres-notify"})
        if hop < MAX_HOPS:
            for e in calls.get(ek, [])[:3]:
                tgt = e["target"]
                remote = handler_of(tgt) if nodes[tgt]["kind"] == "api-endpoint" else tgt
                if not remote or tgt in seen:
                    continue
                label = nodes[tgt]["name"] if nodes[tgt]["kind"] == "api-endpoint" else e["attributes"].get("path", "")
                via = e["attributes"].get("via_resolved")
                if via in nodes and via != tgt:            # the request really travels through a forwarder (e.g. a gate)
                    fwd = handler_of(via) if nodes[via]["kind"] == "api-endpoint" else via
                    if fwd:
                        steps.append({**_synthetic(handler, fwd, "calls", nodes[via]["name"], 0.8), "protocol": "http"})
                        steps.append({**_step(g, e, src=fwd, dst=remote), "label": label, "kind": "forwards"})
                        if nodes[tgt]["kind"] == "api-endpoint":
                            steps += trace(tgt, hop + 1, seen | {tgt})
                        continue
                steps.append({**_step(g, e, src=handler, dst=remote), "label": label})
                if nodes[tgt]["kind"] == "api-endpoint":
                    steps += trace(tgt, hop + 1, seen | {tgt})
        return steps

    flows = []
    eps = sorted((k for k, n in nodes.items() if n["kind"] == "api-endpoint" and handler_of(k)),
                 key=lambda k: (nodes[k]["attributes"].get("path", ""), nodes[k]["attributes"].get("method", "")))
    for ek in eps[:MAX_ENDPOINT_FLOWS]:
        a = nodes[ek]["attributes"]
        label = f"{a.get('method', '')} {a.get('path', '')}".strip()
        head: list[dict[str, Any]] = []
        for c in sorted(callers.get(ek, []), key=lambda c: (nodes[c["source"]]["kind"] != "component", c["source"]))[:1]:
            src = c["source"]
            if entry_of.get(src):
                head += [_step(g, pe) for pe in entry_of[src][:1]]
            elif entry_of.get(parent.get(src, "")):        # the user reaches a UI feature module through its web app
                pe = entry_of[parent[src]][0]
                head += [_step(g, pe), _synthetic(parent[src], src, "uses", "UI module")]
            head.append({**_step(g, c, src=c["source"], dst=handler_of(ek)), "label": label, "kind": "calls"})
        if not head:
            head.append(_synthetic(ek, handler_of(ek), "handles", label))
        steps = head + trace(ek, 1, {ek})
        if len(steps) >= 2:
            f = _finish(g, _fid("endpoint", ek), "endpoint", label, steps[:MAX_STEPS], system_of, entry=ek)
            f["endpoint"] = ek
            flows.append(f)
    return flows


def channel_delivery(g: dict[str, Any], ck: str) -> list[dict[str, Any]]:
    """A NOTIFY channel delivers to every container that LISTENs on it."""
    nodes = g["nodes"]
    return [{**_step(g, e, src=ck, dst=e["source"]), "label": f"LISTEN {nodes[ck]['name']}", "kind": "delivers"}
            for e in g["edges"].values() if e["kind"] == "consumes" and e["target"] == ck
            and nodes.get(e["source"], {}).get("kind") == "container"][:3]


def workflow_steps(g: dict[str, Any], wk: str, depth: int = 0) -> list[dict[str, Any]]:
    """A durable workflow: the worker that executes it, then what its activities do (gateways, MCP servers, stores,
    notifications -> who listens), then its child workflows (one level)."""
    nodes, edges = g["nodes"], g["edges"]
    wf = nodes[wk]
    executors = [e for e in edges.values() if e["kind"] == "consumes" and e["target"] == wk
                 and nodes.get(e["source"], {}).get("kind") == "container"]
    steps: list[dict[str, Any]] = []
    for e in executors[:1]:
        worker = e["source"]
        steps.append({**_step(g, e, src=wk, dst=worker), "label": "executes", "kind": "executes"})
        for fx in wf["attributes"].get("effects", [])[:8]:
            t = fx.get("target")
            if t not in nodes or t == worker:
                continue
            steps.append({**_synthetic(worker, t, fx.get("kind", "calls"), fx.get("label", ""), 0.9),
                          "protocol": "postgres-notify" if nodes[t]["kind"] == "message-channel" else ""})
            if nodes[t]["kind"] == "message-channel":
                steps += channel_delivery(g, t)
            elif nodes[t]["kind"] == "container" and "mcp" in fx.get("label", "").lower():
                # a gateway forwarding MCP calls: to the container that serves MCP tools
                servers = {o for x, xn in nodes.items() if xn["kind"] == "api-endpoint" and xn["attributes"].get("protocol") == "mcp"
                           for o in [owner_of(g, x)] if o}
                steps += [_step(g, x) for x in edges.values() if x["source"] == t and x["kind"] == "calls" and x["target"] in servers][:1]
    if depth == 0:
        for e in edges.values():
            if e["kind"] == "calls" and e["source"] == wk and nodes.get(e["target"], {}).get("kind") == "workflow":
                steps.append({**_step(g, e), "label": f"child {nodes[e['target']]['name']}", "kind": "starts"})
                steps += workflow_steps(g, e["target"], depth + 1)[:4]
    return steps


def _workflow_flow(g: dict[str, Any], wk: str, out_e: dict[str, list[dict[str, Any]]], system_of: dict[str, str]) -> dict[str, Any] | None:
    nodes, edges = g["nodes"], g["edges"]
    starters = [e for e in edges.values() if e["kind"] == "publishes" and e["target"] == wk
                and nodes.get(e["source"], {}).get("kind") == "container"]
    steps = [{**_step(g, e), "label": e["attributes"].get("label", "starts")} for e in starters[:3]]
    steps += workflow_steps(g, wk)
    if not steps:
        return None
    return _finish(g, _fid("event", wk), "event", f"Workflow: {nodes[wk].get('name', wk)}", steps[:MAX_STEPS], system_of, entry=wk)


def owner_of(g: dict[str, Any], endpoint: str) -> str | None:
    for e in g["edges"].values():
        if e["kind"] == "exposes" and e["target"] == endpoint:
            return e["source"]
    return None


def listener_steps(g: dict[str, Any], ck: str, depth: int = 2) -> list[dict[str, Any]]:
    """An in-process event delivered to each listener (as its own entry point), then what that listener does."""
    nodes = g["nodes"]
    out: list[dict[str, Any]] = []
    for x, xn in sorted(nodes.items()):
        a = xn["attributes"]
        if xn["kind"] != "api-endpoint" or ck not in a.get("listens", []) or a.get("method") != "EVENT":
            continue
        comp = a.get("component")
        if comp not in nodes:
            continue
        out.append({**_synthetic(ck, comp, "delivers", a.get("handler", ""), 0.95), "protocol": "in-process event"})
        out += effect_steps(g, comp, a.get("effects", []), comp, depth - 1)
        if len(out) >= MAX_STEPS:
            break
    return out


def effect_steps(g: dict[str, Any], src: str, effects: list[dict[str, str]], skip: str | None, depth: int = 2) -> list[dict[str, Any]]:
    """Steps for a handler's effects; events continue into their listeners and channels into their subscribers."""
    nodes = g["nodes"]
    out: list[dict[str, Any]] = []
    for fx in effects[:8]:
        t = fx.get("target")
        if t not in nodes or t == skip:
            continue
        out.append(_synthetic(src, t, fx.get("kind", "calls"), fx.get("label", ""), 0.9))
        tn = nodes[t]
        if tn["kind"] == "message-channel" and depth > 0:
            if tn["attributes"].get("in_process"):
                out += listener_steps(g, t, depth)
            else:
                out += channel_delivery(g, t)
    return out

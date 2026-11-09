"""Versioned drift rules (AT-DRIFT_ENGINE-001..003). Deterministic: same snapshots + same rule versions ⇒ same findings.

Three-way model: desired = approved baseline; static = code/IaC evidence (origin static); runtime = live evidence.
Coverage decides between drift and UNKNOWN/INCOMPLETE: absence only counts where a fresh, complete scan of the right
origin covers the element (missing evidence is never proof of absence).
"""
from __future__ import annotations

import fnmatch
import hashlib
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

RULES = {
    "DR-MISSING-001": {"version": "1.3", "severity": "high", "title": "Missing element", "requires": ["static|runtime"]},
    "DR-UNPLANNED-001": {"version": "1.0", "severity": "medium", "title": "Unplanned element", "requires": []},
    "DR-EDGE-ADDED-001": {"version": "1.0", "severity": "medium", "title": "Unplanned dependency", "requires": []},
    "DR-EDGE-REMOVED-001": {"version": "1.2", "severity": "high", "title": "Planned dependency missing", "requires": ["static|runtime"]},
    "DR-PROTOCOL-001": {"version": "1.0", "severity": "high", "title": "Protocol changed", "requires": []},
    "DR-RUNTIME-NOT-RUNNING-001": {"version": "1.0", "severity": "high", "title": "Declared but not running", "requires": ["runtime"]},
    "DR-RUNTIME-UNDECLARED-001": {"version": "1.0", "severity": "medium", "title": "Running but not declared", "requires": ["static"]},
    "DR-ACTION-UNROUTED-001": {"version": "1.0", "severity": "high", "title": "Action not routed by the gateway", "requires": ["static"]},
    "DR-ROUTE-NO-ENDPOINT-001": {"version": "1.0", "severity": "high", "title": "Route to a missing backend endpoint", "requires": ["static"]},
    "DR-ADR-FORBID-001": {"version": "1.0", "severity": "high", "title": "Violates an accepted decision (forbidden dependency)", "requires": []},
    "DR-ADR-VIA-001": {"version": "1.0", "severity": "high", "title": "Violates an accepted decision (bypasses the required intermediary)", "requires": []},
    "DR-ADR-REQUIRE-001": {"version": "1.0", "severity": "high", "title": "Violates an accepted decision (required dependency missing)", "requires": ["static|runtime"]},
    "DR-ADR-TECH-001": {"version": "1.0", "severity": "medium", "title": "Violates an accepted decision (technology)", "requires": []},
    "DR-BOUNDARY-001": {"version": "1.0", "severity": "high", "title": "Module boundary violated", "requires": ["static"]},
    "DR-CYCLE-001": {"version": "1.0", "severity": "medium", "title": "Dependency cycle between modules", "requires": ["static"]},
}
CONSTRAINT_TYPES = ("forbid", "require", "only-via", "technology")
ARCH_NODE_KINDS = {"software-system", "container", "external-system", "database", "kafka-topic", "api-contract"}
ARCH_EDGE_KINDS = {"calls", "writes", "reads", "publishes", "consumes"}
OWNED_NODE_KINDS = {"software-system", "container", "api-contract"}   # what a team plans; externals are inferred dependencies
NOISY_WHEN_STALE = {"DR-MISSING-001", "DR-EDGE-REMOVED-001"}           # deleted (not resolved) once no longer produced
PROBE_PATH = re.compile(r"^/(?:health|healthz|livez|readyz|ready|live|metrics|ping|status)(?:/|$)")   # usually framework-provided
MIN_CONFIDENCE = 0.6          # inferred / low-confidence evidence alone never raises drift


@dataclass
class Coverage:
    """Which key prefixes each origin authoritatively covers, and whether that coverage is fresh and complete."""
    by_origin: dict[str, list[tuple[str, str]]] = field(default_factory=dict)   # origin -> [(prefix, freshness status)]

    @classmethod
    def from_inputs(cls, inputs: list[dict[str, Any]]) -> Coverage:
        c = cls()
        for i in inputs:
            cov = i.get("coverage") or {}
            origin = cov.get("origin")
            status = (i.get("freshness") or {}).get("status", "unknown")
            for p in cov.get("prefixes", []):
                c.by_origin.setdefault(origin, []).append((p, status))
        return c

    def status(self, origin: str, key: str) -> str:
        """current | stale | incomplete | unknown (= not covered at all)."""
        best = "unknown"
        rank = {"current": 3, "incomplete": 2, "stale": 1, "unknown": 0}
        for p, st in self.by_origin.get(origin, []):
            if (key.startswith(p) or key == p.rstrip("/")) and rank[st] > rank[best]:
                best = st
        return best

    def for_edge(self, origin: str, edge: dict[str, Any]) -> str:
        a, b = self.status(origin, edge["source"]), self.status(origin, edge["target"])
        rank = {"current": 3, "incomplete": 2, "stale": 1, "unknown": 0}
        return a if rank[a] <= rank[b] else b


def finding_id(project_id: uuid.UUID, rule_id: str, subject: str) -> uuid.UUID:
    """Stable identity: independent of snapshot and rule version, so re-evaluation updates the same finding."""
    return uuid.UUID(hashlib.sha256(f"{project_id}|{rule_id}|{subject}".encode()).hexdigest()[:32])


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _verdict(cov_status: str) -> str:
    return {"current": "drift", "incomplete": "incomplete", "stale": "unknown", "unknown": "unknown"}[cov_status]


def _strong(x: dict[str, Any], origin: str | None = None) -> bool:
    if float(x.get("confidence", 1)) < MIN_CONFIDENCE or x.get("inferred_only"):
        return False
    return origin is None or origin in x.get("origins", [])


def _significant_node(n: dict[str, Any]) -> bool:
    """Architecture-level elements a team plans; volumes, one-shot jobs and optional profiles are not drift material."""
    a = n.get("attributes", {})
    st = n.get("by_origin", {}).get("static", {})
    return not (a.get("volume") or st.get("one_shot") or st.get("optional") or a.get("subtype") in ("volume", "test"))


def _significant_edge(e: dict[str, Any]) -> bool:
    a = e.get("attributes", {})
    return a.get("purpose") != "health check" and a.get("rollup") != "from components" or e.get("kind") in ("writes", "publishes")


def _match(pattern: str, key: str, node: dict[str, Any] | None) -> bool:
    """A constraint end: an element key, a key prefix ending in '*', or a name (glob, case-insensitive)."""
    p = pattern.strip().lower()
    if not p:
        return False
    if p == key.lower() or (p.endswith("*") and key.lower().startswith(p[:-1])):
        return True
    return node is not None and fnmatch.fnmatch(_norm(node.get("name", "")), _norm(p).replace("\\*", "*") if "*" in p else _norm(p))


def _rels(c: dict[str, Any]) -> set[str]:
    r = str(c.get("relation") or "any").lower()
    return set(ARCH_EDGE_KINDS) if r in ("any", "", "*") else {x.strip() for x in r.split(",")}


def conformance(adrs: list[dict[str, Any]], current: dict[str, Any], cov: Coverage) -> list[dict[str, Any]]:
    """Accepted decisions with machine-checkable constraints, evaluated deterministically on the current graph."""
    cn, ce = current["nodes"], current["edges"]
    out: list[dict[str, Any]] = []
    for adr in adrs:
        ref = f"ADR-{adr.get('number', '?'):03d}" if isinstance(adr.get("number"), int) else "ADR"
        for i, c in enumerate(adr.get("constraints") or []):
            t = str(c.get("type", "")).lower()
            base = {"adr_id": str(adr.get("id", "")), "adr": ref, "adr_title": adr.get("title", ""), "constraint": c}
            label = c.get("description") or ""
            if t in ("forbid", "only-via"):
                for k, e in ce.items():
                    if e["kind"] not in _rels(c) or not _strong(e) or not _significant_edge(e):
                        continue
                    src, tgt = e["source"], e["target"]
                    if not _match(str(c.get("to", "")), tgt, cn.get(tgt)):
                        continue
                    if t == "forbid" and _match(str(c.get("from", "*")), src, cn.get(src)):
                        out.append({"rule_id": "DR-ADR-FORBID-001", "subject_key": f"{ref}#{i}|{k}", "verdict": "drift",
                                    "title": f"{cn.get(src, {}).get('name', src)} {e['kind']} {cn.get(tgt, {}).get('name', tgt)}, "
                                             f"which {ref} forbids{(': ' + label) if label else ''}",
                                    "expected": {**base, "forbidden": f"{c.get('from', '*')} → {c.get('to')}"},
                                    "actual": {"edge": k, "protocol": e["attributes"].get("protocol")}, "evidence": e.get("evidence", [])[:3]})
                    elif t == "only-via" and not _match(str(c.get("via", "")), src, cn.get(src)) and \
                            not _match(str(c.get("allow", "")), src, cn.get(src)):
                        out.append({"rule_id": "DR-ADR-VIA-001", "subject_key": f"{ref}#{i}|{k}", "verdict": "drift",
                                    "title": f"{cn.get(src, {}).get('name', src)} reaches {cn.get(tgt, {}).get('name', tgt)} directly; "
                                             f"{ref} requires going through {c.get('via')}",
                                    "expected": {**base, "via": c.get("via")}, "actual": {"edge": k}, "evidence": e.get("evidence", [])[:3]})
            elif t == "require":
                srcs = [k for k, n in cn.items() if _match(str(c.get("from", "")), k, n)]
                tgts = {k for k, n in cn.items() if _match(str(c.get("to", "")), k, n)}
                if not srcs or not tgts:
                    continue                     # the decision's elements are not (yet) observed: nothing to judge
                ok = any(e["source"] in srcs and e["target"] in tgts and e["kind"] in _rels(c) for e in ce.values())
                if not ok:
                    st = max((cov.status(o, srcs[0]) for o in ("static", "runtime")),
                             key=lambda s: ["unknown", "stale", "incomplete", "current"].index(s))
                    out.append({"rule_id": "DR-ADR-REQUIRE-001", "subject_key": f"{ref}#{i}", "verdict": _verdict(st),
                                "title": f"{ref} requires {c.get('from')} → {c.get('to')}, which is not observed",
                                "expected": base, "actual": None, "evidence": []})
            elif t == "technology":
                want = str(c.get("technology", "")).lower()
                for k, n in cn.items():
                    if not want or not _match(str(c.get("element", "")), k, n):
                        continue
                    a = n.get("attributes", {})
                    have = " ".join(str(a.get(x, "")) for x in ("technology", "image", "language", "subtype")).lower()
                    if have.strip() and want not in have:
                        out.append({"rule_id": "DR-ADR-TECH-001", "subject_key": f"{ref}#{i}|{k}", "verdict": "drift",
                                    "title": f"{n.get('name', k)} uses {have.strip()[:60]}, but {ref} decided {c.get('technology')}",
                                    "expected": {**base, "technology": c.get("technology")}, "actual": {"technology": have.strip()[:120]},
                                    "evidence": n.get("evidence", [])[:3]})
    for f in out:
        f["rule_version"], f["severity"] = RULES[f["rule_id"]]["version"], RULES[f["rule_id"]]["severity"]
    return out


def evaluate(baseline: dict[str, Any] | None, current: dict[str, Any], cov: Coverage,
             adrs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Pure evaluation over materialized graphs. Returns findings (without IDs); verdict drift|unknown|incomplete."""
    out: list[dict[str, Any]] = []

    def add(rule, subject, title, verdict, expected=None, actual=None, evidence=None):
        out.append({"rule_id": rule, "rule_version": RULES[rule]["version"], "severity": RULES[rule]["severity"],
                    "subject_key": subject, "title": title, "verdict": verdict, "expected": expected, "actual": actual,
                    "evidence": evidence or []})

    cn, ce = current["nodes"], current["edges"]
    if baseline is not None:
        bn, be = baseline["nodes"], baseline["edges"]
        names = {_norm(n["name"]) for n in cn.values()}
        for k, n in bn.items():
            if n["kind"] not in ARCH_NODE_KINDS or k in cn:
                continue
            if n["kind"] not in OWNED_NODE_KINDS or _norm(n["name"]) in names:
                continue                 # an external dependency stopped being inferred, or the element was re-keyed: not drift
            st = max((cov.status(o, k) for o in ("static", "runtime")), key=lambda s: ["unknown", "stale", "incomplete", "current"].index(s))
            if _verdict(st) == "unknown":
                continue                 # no current source covers it any more: "not observed" says nothing (no finding)
            add("DR-MISSING-001", k, f"{n['name']} is in the approved baseline but no longer observed", _verdict(st),
                expected={"kind": n["kind"], "name": n["name"]}, actual=None, evidence=n.get("evidence", [])[:3])
        unplanned: set[str] = set()
        for k, n in cn.items():
            if n["kind"] in ARCH_NODE_KINDS and k not in bn and _strong(n) and _significant_node(n):
                unplanned.add(k)
                new_deps = sorted({f"{e['source']} {e['kind']} {e['target']}" for e in ce.values()
                                   if k in (e["source"], e["target"]) and e["kind"] in ARCH_EDGE_KINDS})[:12]
                add("DR-UNPLANNED-001", k, f"{n['name']} exists but is not in the approved baseline", "drift",
                    expected=None, actual={"kind": n["kind"], "origins": n["origins"], "dependencies": new_deps},
                    evidence=n.get("evidence", [])[:3])
        unplanned |= {k for k in cn if k not in bn}
        current_pairs = {(e["kind"], _norm(cn[e["source"]]["name"]), _norm(cn[e["target"]]["name"])) for e in ce.values()
                         if e["source"] in cn and e["target"] in cn}
        for k, e in be.items():
            if e["kind"] not in ARCH_EDGE_KINDS or k in ce:
                continue
            if e["source"] not in cn or e["target"] not in cn:
                continue                 # an end disappeared or was re-keyed: reported (if at all) on the element, not per edge
            if (e["kind"], _norm(cn[e["source"]]["name"]), _norm(cn[e["target"]]["name"])) in current_pairs:
                continue
            if cn[e["source"]]["kind"] not in OWNED_NODE_KINDS or cn[e["target"]]["kind"] not in OWNED_NODE_KINDS:
                continue                 # dependencies on externals are inferred from library use: their absence is not drift
            st = max((cov.for_edge(o, e) for o in ("static", "runtime")), key=lambda s: ["unknown", "stale", "incomplete", "current"].index(s))
            add("DR-EDGE-REMOVED-001", k, f"Planned {e['kind']} {e['source']} → {e['target']} is no longer observed", _verdict(st),
                expected={"kind": e["kind"], "protocol": e["attributes"].get("protocol")}, evidence=e.get("evidence", [])[:3])
        for k, e in ce.items():
            if e["source"] in unplanned or e["target"] in unplanned:
                continue                 # reported once, on the new element (with its dependencies), not once per edge
            if cn.get(e["source"], {}).get("kind") not in ARCH_NODE_KINDS or cn.get(e["target"], {}).get("kind") not in ARCH_NODE_KINDS:
                continue                 # code/component-level wiring is not an architecture decision
            if e["kind"] in ARCH_EDGE_KINDS and k not in be and _strong(e) and _significant_edge(e):
                add("DR-EDGE-ADDED-001", k, f"New {e['kind']} {e['source']} → {e['target']} is not in the approved baseline", "drift",
                    actual={"kind": e["kind"], "protocol": e["attributes"].get("protocol"), "origins": e["origins"]},
                    evidence=e.get("evidence", [])[:3])
            elif k in be:
                pb, pc = be[k]["attributes"].get("protocol"), e["attributes"].get("protocol")
                if pb and pc and pb != pc:
                    add("DR-PROTOCOL-001", k, f"Protocol of {e['source']} → {e['target']} changed from {pb} to {pc}", "drift",
                        expected={"protocol": pb}, actual={"protocol": pc}, evidence=e.get("evidence", [])[:3])
    # cross-service contracts in code (independent of the baseline): a caller and the service it calls disagree
    for k, n in cn.items():
        for u in n["attributes"].get("unrouted_actions") or []:
            gw = cn.get(u["gateway"], {}).get("name", u["gateway"])
            add("DR-ACTION-UNROUTED-001", f"{k}#action:{u['action']}",
                f"{n['name']} sends action {u['action']} but {gw} does not route it", "drift",
                expected={"routed_by": gw}, actual={"action": u["action"], "sent_from": f"{u.get('path', '')}:{u.get('line') or ''}"},
                evidence=[u["evidence"]] if u.get("evidence") else [])
    exposes = {e["source"] for e in ce.values() if e["kind"] == "exposes"}
    for k, e in ce.items():
        src, tgt = cn.get(e["source"], {}), cn.get(e["target"], {})
        a = e["attributes"]
        if (e["kind"] == "calls" and src.get("kind") == "api-endpoint" and tgt.get("kind") == "container" and a.get("path")
                and e["target"] in exposes and _strong(e) and not PROBE_PATH.search(str(a["path"]))):
            add("DR-ROUTE-NO-ENDPOINT-001", k,
                f"{src['name']} is routed to {a.get('method', '')} {a['path']}, which {tgt['name']} does not expose".replace("  ", " "),
                "drift", expected={"endpoint": f"{a.get('method', '')} {a['path']}".strip(), "service": tgt["name"]},
                actual={"exposed_by_service": "no matching endpoint"}, evidence=e.get("evidence", [])[:3])
    # static vs runtime (independent of the baseline)
    for k, n in cn.items():
        if n["kind"] != "container":
            continue
        origins = set(n.get("origins", []))
        attrs_rt = n.get("by_origin", {}).get("runtime", {})
        attrs_st = n.get("by_origin", {}).get("static", {})
        if "static" in origins and not attrs_st.get("optional") and not attrs_st.get("one_shot"):
            rt_cov = cov.status("runtime", k)
            if rt_cov == "unknown":
                continue                                    # no runtime connector covers this system: nothing to say
            if "runtime" not in origins or (attrs_rt and not attrs_rt.get("running", True)):
                state = attrs_rt.get("status") or "no container"
                add("DR-RUNTIME-NOT-RUNNING-001", k, f"{n['name']} is declared in code but not running ({state})", _verdict(rt_cov),
                    expected={"declared_in": attrs_st.get("compose_file")}, actual={"runtime": state or "absent"},
                    evidence=n.get("evidence", [])[:3])
        if "runtime" in origins and "static" not in origins and attrs_rt.get("running", True):
            st_cov = cov.status("static", k)
            if st_cov != "unknown":
                add("DR-RUNTIME-UNDECLARED-001", k, f"{n['name']} is running but not declared in code", _verdict(st_cov),
                    actual={"image": attrs_rt.get("image"), "container": attrs_rt.get("container_name")},
                    evidence=n.get("evidence", [])[:3])
    # module boundaries declared in code (Spring Modulith modules, allowedDependencies) and dependency cycles between modules
    for k, e in ce.items():
        if e["kind"] != "depends-on" or cn.get(e["source"], {}).get("kind") != "component":
            continue
        a = e["attributes"]
        sname, tname = cn[e["source"]]["name"], cn.get(e["target"], {}).get("name", e["target"])
        if a.get("boundary_violation"):
            add("DR-BOUNDARY-001", k, f"{sname} uses {tname}'s internals ({a['boundary_violation']})", "drift",
                expected={"rule": "modules use each other only through their public API / named interfaces"},
                actual={"internal_types": a.get("internal_access", [])[:10]}, evidence=e.get("evidence", [])[:3])
        if a.get("cycle"):
            add("DR-CYCLE-001", k, f"{sname} → {tname} is part of a dependency cycle between modules", "drift",
                expected={"rule": "module dependencies form a directed acyclic graph"}, actual={"types": a.get("types", [])[:10]},
                evidence=e.get("evidence", [])[:3])
    out += conformance(adrs or [], current, cov)
    return sorted(out, key=lambda f: (f["rule_id"], f["subject_key"]))

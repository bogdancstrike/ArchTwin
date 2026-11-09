"""Deterministic graph builder (AT-ARCHITECTURE_GRAPH-002): pure function from observations to nodes/edges.

Same inputs ⇒ same output and same manifest hash (golden-tested). Identity aliases map alias keys onto canonical keys.
Kind/name precedence: manual > desired > static > runtime > inferred. Low-confidence inferred-only elements are kept but
flagged `inferred_only` so they are never shown as established facts.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any

BUILDER_VERSION = "graph-builder/1.2"
ORIGIN_RANK = {"manual": 0, "desired": 1, "static": 2, "runtime": 3, "planned": 4, "issue": 5, "inferred": 6}
VOLATILE_ATTRS = {"status", "observed_at"}            # excluded from the manifest hash (they change every scan)
MAX_EVIDENCE = 8


def _canon(key: str, aliases: dict[str, str]) -> str:
    seen = set()
    while key in aliases and key not in seen:
        seen.add(key)
        key = aliases[key]
    return key


def _evidence(o: dict[str, Any]) -> dict[str, Any]:
    return {"observation_id": str(o["id"]), "connector_id": str(o["connector_id"]) if o.get("connector_id") else None,
            "origin": o["origin"], "source_ref": o.get("source_ref", ""), "source_revision": o.get("source_revision", ""),
            "observed_at": o["observed_at"].isoformat() if hasattr(o.get("observed_at"), "isoformat") else o.get("observed_at"),
            "parser_version": o["parser_version"], "confidence": float(o["confidence"]), "span": o.get("evidence") or {}}


RESOLVABLE = ("container", "software-system", "database", "external-system", "service")
GENERIC_NAMES = {"api", "app", "web", "db", "data", "worker", "server", "client", "service", "backend", "frontend", "main", "core",
                 "test", "tests", "docs", "admin", "user", "users", "cache", "proxy", "gateway", "queue", "jobs", "job", "ui"}


def _norm(x: str) -> str:
    return re.sub(r"[\s_]+", "-", x.strip().lower())


def _name_index(nodes: dict[str, dict[str, Any]]) -> dict[str, dict[str, set[str]]]:
    """normalized name -> {kind: {node keys}} over elements that a name in another datasource may refer to."""
    idx: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for k, n in nodes.items():
        if n["kind"] not in RESOLVABLE:
            continue
        leaf = k.split(":", 1)[-1].rsplit("/", 1)[-1]
        for name in {n.get("name", ""), leaf}:
            if name:
                idx[_norm(name)][n["kind"]].add(k)
    return idx


def _resolve(name: str, idx: dict[str, dict[str, set[str]]], exclude: str) -> str | None:
    by_kind = idx.get(_norm(name))
    if not by_kind:
        return None
    for kind in ("container", "database", "service", "software-system", "external-system"):   # most specific first
        cands = by_kind.get(kind, set()) - {exclude}
        if len(cands) == 1:
            return next(iter(cands))
        if len(cands) > 1:
            return None                                        # ambiguous: never guess
    return None


def resolve_names(nodes: dict[str, dict[str, Any]], edges: dict[str, dict[str, Any]]) -> list[str]:
    """Edges whose endpoint is `name:<x>` (cross-repository config URLs, diagrams in docs) are re-pointed to the unique element
    with that name in ANY datasource; ambiguous or unknown names are dropped (and reported), never invented."""
    pending = [k for k, e in edges.items() if e["source"].startswith("name:") or e["target"].startswith("name:")]
    if not pending:
        return []
    idx = _name_index(nodes)
    unresolved: set[str] = set()
    for k in pending:
        e = edges.pop(k)
        src = e["source"] if not e["source"].startswith("name:") else _resolve(e["source"][5:], idx, "")
        dst = e["target"] if not e["target"].startswith("name:") else _resolve(e["target"][5:], idx, src or "")
        if not src or not dst or src == dst:
            unresolved.update(x[5:] for x, r in ((e["source"], src), (e["target"], dst)) if x.startswith("name:") and not r)
            continue
        nk = f"{src}|{e['kind']}|{dst}"
        cur = edges.get(nk)
        if cur is None:
            edges[nk] = {**e, "key": nk, "source": src, "target": dst}
            continue
        cur["origins"] |= e["origins"]                     # corroboration: e.g. code and a documented diagram agree
        cur["confidence"] = max(cur["confidence"], e["confidence"])
        for o, attrs in e["by_origin"].items():
            cur["by_origin"].setdefault(o, attrs)
        for a, v in e["attributes"].items():
            cur["attributes"].setdefault(a, v)
        cur["evidence"] = (cur["evidence"] + e["evidence"])[:MAX_EVIDENCE]
    return sorted(unresolved)[:200]


def link_mentions(nodes: dict[str, dict[str, Any]], edges: dict[str, dict[str, Any]]) -> None:
    """ADRs and work items (Taiga / GitLab / GitHub) `references` the containers and systems their title names explicitly
    (whole word, distinctive names only): inferred, low confidence, never used for drift."""
    targets: list[tuple[re.Pattern[str], str]] = []
    for k, n in nodes.items():
        if n["kind"] not in ("container", "software-system", "database"):
            continue
        name = n.get("name") or ""
        if len(name) < 4 or _norm(name) in GENERIC_NAMES:
            continue
        pat = re.escape(_norm(name)).replace("\\-", "[-_ ]")
        targets.append((re.compile(rf"(?<![\w-]){pat}(?![\w-])", re.IGNORECASE), k))
    if not targets:
        return
    for k, n in list(nodes.items()):
        if n["kind"] not in ("adr", "work-item"):
            continue
        text = f"{n.get('name', '')} {n['attributes'].get('path', '')}"
        hits = [t for rx, t in targets if rx.search(text)][:5]
        for t in hits:
            ek = f"{k}|references|{t}"
            if ek in edges:
                continue
            ev = (n.get("evidence") or [{}])[:1]
            edges[ek] = {"key": ek, "kind": "references", "source": k, "target": t, "attributes": {"detected_by": "name mention"},
                         "by_origin": {"inferred": {"detected_by": "name mention"}}, "origins": {"inferred"}, "confidence": 0.5,
                         "evidence": [{**ev[0], "origin": "inferred", "parser_version": "mention-link/1.0", "confidence": 0.5}] if ev else []}


def build(obs: list[dict[str, Any]], aliases: dict[str, str] | None = None) -> dict[str, Any]:
    aliases = aliases or {}
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    retracted: set[str] = set()
    for o in sorted(obs, key=lambda o: (ORIGIN_RANK.get(o["origin"], 9), o["subject_key"], str(o["id"]))):
        attrs = dict(o.get("attributes") or {})
        if o["origin"] == "manual" and attrs.get("retracted"):
            retracted.add(_canon(o["subject_key"], aliases))
            continue
        if o["subject_kind"] == "node":
            k = _canon(o["subject_key"], aliases)
            n = nodes.setdefault(k, {"key": k, "kind": o["kind"], "name": o["name"], "attributes": {}, "by_origin": {},
                                     "origins": set(), "confidence": 0.0, "evidence": [], "sensitive": False})
            n["origins"].add(o["origin"])
            n["confidence"] = max(n["confidence"], float(o["confidence"]))
            n["sensitive"] = n["sensitive"] or bool(o.get("sensitive"))
            bo = n["by_origin"].setdefault(o["origin"], {})
            for a, v in attrs.items():
                bo.setdefault(a, v)
                n["attributes"].setdefault(a, v)   # higher-precedence origin was applied first
            if len(n["evidence"]) < MAX_EVIDENCE:
                n["evidence"].append(_evidence(o))
        else:
            src, dst = _canon(attrs.get("source", ""), aliases), _canon(attrs.get("target", ""), aliases)
            k = f"{src}|{o['kind']}|{dst}"
            e = edges.setdefault(k, {"key": k, "kind": o["kind"], "source": src, "target": dst, "attributes": {}, "by_origin": {},
                                     "origins": set(), "confidence": 0.0, "evidence": []})
            e["origins"].add(o["origin"])
            e["confidence"] = max(e["confidence"], float(o["confidence"]))
            bo = e["by_origin"].setdefault(o["origin"], {})
            for a, v in attrs.items():
                if a in ("source", "target"):
                    continue
                bo.setdefault(a, v)
                e["attributes"].setdefault(a, v)
            if len(e["evidence"]) < MAX_EVIDENCE:
                e["evidence"].append(_evidence(o))
    for k in retracted:
        nodes.pop(k, None)
    unresolved = resolve_names(nodes, edges)
    link_mentions(nodes, edges)
    dropped = []
    for k in list(edges):
        e = edges[k]
        if e["source"] not in nodes or e["target"] not in nodes or k in retracted or e["source"] == e["target"]:
            dropped.append(k)
            del edges[k]
    for coll in (nodes, edges):
        for x in coll.values():
            x["origins"] = sorted(x["origins"], key=lambda s: ORIGIN_RANK.get(s, 9))
            x["inferred_only"] = x["origins"] == ["inferred"]
            x["confidence"] = round(x["confidence"], 3)
    return {"nodes": dict(sorted(nodes.items())), "edges": dict(sorted(edges.items())), "dropped_edges": sorted(dropped),
            "unresolved_names": unresolved,
            "manifest_hash": manifest_hash(nodes, edges)}


def _stable(x: dict[str, Any]) -> dict[str, Any]:
    return {"key": x["key"], "kind": x["kind"], "name": x.get("name", ""), "origins": x["origins"],
            "attributes": {k: v for k, v in sorted(x["attributes"].items()) if k not in VOLATILE_ATTRS}}


def element_hash(x: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(_stable(x), sort_keys=True, default=str).encode()).hexdigest()[:16]


def manifest_hash(nodes: dict[str, Any], edges: dict[str, Any]) -> str:
    h = hashlib.sha256()
    for k in sorted(nodes):
        h.update(f"N|{k}|{element_hash(nodes[k])}\n".encode())
    for k in sorted(edges):
        h.update(f"E|{k}|{element_hash(edges[k])}\n".encode())
    return h.hexdigest()


def diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Diff two materialized graphs {'nodes':{key:..}, 'edges':{key:..}} (a = older, b = newer)."""
    out: dict[str, Any] = {}
    for coll in ("nodes", "edges"):
        ak, bk = set(a[coll]), set(b[coll])
        changed = []
        for k in sorted(ak & bk):
            if element_hash(a[coll][k]) != element_hash(b[coll][k]):
                before, after = a[coll][k]["attributes"], b[coll][k]["attributes"]
                fields = sorted(f for f in set(before) | set(after) if before.get(f) != after.get(f) and f not in VOLATILE_ATTRS)
                if a[coll][k]["origins"] != b[coll][k]["origins"]:
                    fields.append("origins")
                changed.append({"key": k, "fields": fields, "before": {f: before.get(f) for f in fields if f != "origins"},
                                "after": {f: after.get(f) for f in fields if f != "origins"}})
        out[coll] = {"added": sorted(bk - ak), "removed": sorted(ak - bk), "changed": changed}
    out["summary"] = {f"{c}_{k}": len(out[c][k]) for c in ("nodes", "edges") for k in ("added", "removed", "changed")}
    return out


def suggestions(nodes: dict[str, Any]) -> list[tuple[str, str, float, str]]:
    """Identity reconciliation suggestions: same leaf name, same kind, different keys (e.g. docker/x vs compose/x)."""
    by_leaf: dict[tuple[str, str], list[str]] = defaultdict(list)
    for k, n in nodes.items():
        if n["kind"] in ("container", "software-system", "database"):
            by_leaf[(n["kind"], k.rsplit("/", 1)[-1].lower())].append(k)
    out = []
    for (_, leaf), keys in sorted(by_leaf.items()):
        keys = sorted(keys)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = keys[i], keys[j]
                oa, ob = set(nodes[a]["origins"]), set(nodes[b]["origins"])
                if oa != ob and (oa | ob) >= {"static", "runtime"} and (oa & ob) != (oa | ob):
                    out.append((a, b, 0.7, f"same name '{leaf}' observed by different origins"))
    return out

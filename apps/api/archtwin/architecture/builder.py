"""Deterministic graph builder (AT-ARCHITECTURE_GRAPH-002): pure function from observations to nodes/edges.

Same inputs ⇒ same output and same manifest hash (golden-tested). Identity aliases map alias keys onto canonical keys.
Kind/name precedence: manual > desired > static > runtime > inferred. Low-confidence inferred-only elements are kept but
flagged `inferred_only` so they are never shown as established facts.
"""
from __future__ import annotations

import hashlib
import json
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

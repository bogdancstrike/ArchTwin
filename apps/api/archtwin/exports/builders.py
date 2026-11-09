"""Markdown builders, one per exported resource (pure functions over the data the pages show).

Each builder returns Markdown with a provenance line, tables for the data and Mermaid blocks for diagrams, so the export
reads well in any Markdown viewer and converts cleanly to DOCX/PDF.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

MAX_ROWS = 3000
SYSTEM_KINDS = {"software-system"}
EXTERNAL_KINDS = {"external-system", "database", "person", "kafka-topic", "volume"}


def cell(v: Any) -> str:
    s = "" if v is None else str(v)
    return s.replace("|", "\\|").replace("\n", " ").strip()[:400]


def table(head: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_None._\n"
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows[:MAX_ROWS]]
    if len(rows) > MAX_ROWS:
        out.append(f"\n_{len(rows) - MAX_ROWS} more rows not shown._")
    return "\n".join(out) + "\n"


def _mid(key: str) -> str:
    return "n_" + re.sub(r"[^A-Za-z0-9_]", "_", key)[-60:]


def _label(s: str) -> str:
    return re.sub(r'["\[\](){}<>|#;]', " ", s or "").strip()[:60] or "?"


def provenance(project: str, snapshot: dict[str, Any] | None, now: datetime | None = None) -> str:
    when = (now or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M UTC")
    snap = f"snapshot v{snapshot['version']}" if snapshot else "no snapshot yet"
    return f"> Exported from ArchTwin · project **{project}** · {snap} · {when}. Every fact comes from scanned evidence.\n"


# ------------------------------------------------------------------ architecture
def _parents(g: dict[str, Any]) -> dict[str, str]:
    return {e["target"]: e["source"] for e in g["edges"].values() if e["kind"] in ("contains", "exposes")}


def _system_of(g: dict[str, Any]) -> dict[str, str]:
    par = _parents(g)
    out = {}
    for k in g["nodes"]:
        cur, seen = k, set()
        while cur in par and cur not in seen:
            seen.add(cur)
            cur = par[cur]
        out[k] = cur
    return out


def _flowchart(nodes: dict[str, dict[str, Any]], pairs: set[tuple[str, str, str]], direction: str = "LR") -> str:
    lines = [f"flowchart {direction}"]
    for k, n in nodes.items():
        shape = ("[(", ")]") if n["kind"] == "database" else ("([", "])") if n["kind"] in EXTERNAL_KINDS else ("[", "]")
        lines.append(f'  {_mid(k)}{shape[0]}"{_label(n["name"])}"{shape[1]}')
    for s, kind, t in sorted(pairs)[:150]:
        lines.append(f"  {_mid(s)} -->|{_label(kind)}| {_mid(t)}")
    return "```mermaid\n" + "\n".join(lines) + "\n```\n"


def architecture_md(g: dict[str, Any], project: str) -> str:
    nodes, edges = g.get("nodes") or {}, g.get("edges") or {}
    sysof = _system_of(g)
    par = _parents(g)
    counts = Counter(n["kind"] for n in nodes.values())
    out = [f"# {project} — Architecture model", "", provenance(project, g.get("snapshot")), "## Overview", "",
           table(["Element kind", "Count"], [[k, v] for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]),
           f"{len(edges)} relationships in total.", ""]
    rel = [e for e in edges.values() if e["kind"] not in ("contains", "exposes")]
    # L1: systems and externals, with relationships rolled up to the systems that contain the ends
    tops = {k: n for k, n in nodes.items() if n["kind"] in SYSTEM_KINDS | EXTERNAL_KINDS and sysof.get(k) == k}
    pairs = {(sysof[e["source"]], e["kind"], sysof[e["target"]]) for e in rel
             if sysof.get(e["source"]) in tops and sysof.get(e["target"]) in tops and sysof[e["source"]] != sysof[e["target"]]}
    out += ["## Level 1 — System context", "", _flowchart(tops, pairs), ""]
    # L2: per system, its containers and what they talk to
    children: dict[str, list[str]] = defaultdict(list)
    for c, p in par.items():
        children[p].append(c)
    for sk in sorted(k for k, n in nodes.items() if n["kind"] in SYSTEM_KINDS):
        s = nodes[sk]
        cont = sorted(c for c in children.get(sk, []) if nodes.get(c, {}).get("kind") == "container")
        out += [f"## Level 2 — {s['name']}", "", s.get("attributes", {}).get("description", "") or "", ""]
        if cont:
            inner = {c: nodes[c] for c in cont}
            ext_pairs = set()
            for e in rel:
                if e["source"] in inner and e["target"] in nodes and e["target"] != e["source"]:
                    tgt = e["target"] if e["target"] in inner else sysof.get(e["target"], e["target"])
                    if tgt in nodes:
                        inner.setdefault(tgt, nodes[tgt])
                        ext_pairs.add((e["source"], e["kind"], tgt))
            out += [_flowchart(inner, ext_pairs), ""]
            out += [table(["Container", "Technology", "Type", "Components"],
                          [[nodes[c]["name"], nodes[c].get("attributes", {}).get("technology", ""), nodes[c].get("attributes", {}).get("subtype", ""),
                            sum(1 for x in children.get(c, []) if nodes.get(x, {}).get("kind") == "component")] for c in cont]), ""]
        # L3: components per container
        for c in cont:
            comps = sorted(x for x in children.get(c, []) if nodes.get(x, {}).get("kind") == "component")
            if comps:
                out += [f"### Level 3 — {nodes[c]['name']} components", "",
                        table(["Component", "Responsibility / module", "Source"],
                              [[nodes[x]["name"], nodes[x].get("attributes", {}).get("module", "") or nodes[x].get("attributes", {}).get("description", ""),
                                nodes[x].get("attributes", {}).get("path", "")] for x in comps]), ""]
    eps = [(k, n) for k, n in nodes.items() if n["kind"] == "api-endpoint"]
    out += ["## API endpoints", "", table(["Method", "Path", "Exposed by", "Handler"],
                                          [[n["attributes"].get("method", ""), n["attributes"].get("path", n["name"]),
                                            nodes.get(par.get(k, ""), {}).get("name", ""), nodes.get(n["attributes"].get("component", ""), {}).get("name", "")]
                                           for k, n in sorted(eps, key=lambda kv: (kv[1]["attributes"].get("path", ""), kv[1]["attributes"].get("method", "")))]), ""]
    ext = [n for k, n in nodes.items() if n["kind"] in EXTERNAL_KINDS]
    out += ["## Data stores and external systems", "", table(["Name", "Kind", "Technology"],
                                                              [[n["name"], n["kind"], n.get("attributes", {}).get("technology", "")]
                                                               for n in sorted(ext, key=lambda n: n["name"].lower())]), ""]
    name = {k: n["name"] for k, n in nodes.items()}
    out += ["## Relationships", "", table(["Source", "Relation", "Target", "Protocol", "Origins", "Confidence"],
                                          [[name.get(e["source"], e["source"]), e["kind"], name.get(e["target"], e["target"]),
                                            e.get("attributes", {}).get("protocol", ""), ", ".join(e.get("origins", [])), e.get("confidence", "")]
                                           for e in sorted(rel, key=lambda e: (name.get(e["source"], ""), e["kind"]))]), ""]
    return "\n".join(out)


# ------------------------------------------------------------------ flows
def flow_md(f: dict[str, Any], level: int = 1) -> str:
    h = "#" * level
    name = {p["key"]: p["name"] for p in f.get("participants", [])}
    meta = [f"kind **{f['kind']}**", f"confidence {f.get('confidence', 1)}", f"{f.get('length', len(f.get('steps', [])))} steps"]
    if f.get("distributed"):
        meta.append("across " + ", ".join(f.get("systems", [])))
    seq = ["sequenceDiagram"]
    alias = {k: f"p{i}" for i, k in enumerate(name)}
    for k, n in name.items():
        seq.append(f"  participant {alias[k]} as {_label(n)}")
    for s in f.get("steps", [])[:60]:
        arrow = "-->>" if s.get("inferred_only") or s.get("documented") else "->>"
        seq.append(f"  {alias.get(s['from'], 'p0')}{arrow}{alias.get(s['to'], 'p0')}: {_label(str(s.get('label') or s.get('kind')))}")
    return "\n".join([f"{h} {f['name']}", "", " · ".join(meta), "",
                      "**Participants, in order:** " + " → ".join(p["name"] for p in f.get("participants", [])), "",
                      "```mermaid\n" + "\n".join(seq) + "\n```", "",
                      table(["#", "From", "Relation", "To", "Label", "Protocol", "Origins", "Confidence"],
                            [[i, name.get(s["from"], s["from"]), s.get("kind", ""), name.get(s["to"], s["to"]), s.get("label", ""), s.get("protocol", ""),
                              ", ".join(s.get("origins", [])), s.get("confidence", "")] for i, s in enumerate(f.get("steps", []), 1)]), ""])


def flows_md(flows: list[dict[str, Any]], project: str, snapshot: dict[str, Any] | None) -> str:
    counts = Counter(f["kind"] for f in flows)
    out = [f"# {project} — Flows", "", provenance(project, snapshot), "## Index", "",
           table(["#", "Flow", "Kind", "Steps", "Systems"], [[i, f["name"], f["kind"], f.get("length", 0), ", ".join(f.get("systems", []))]
                                                             for i, f in enumerate(flows, 1)]),
           "Counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), ""]
    out += [flow_md(f, 2) for f in flows]
    return "\n".join(out)


# ------------------------------------------------------------------ drift
def drift_md(findings: list[dict[str, Any]], project: str, snapshot: dict[str, Any] | None, filters: dict[str, str | None]) -> str:
    flt = ", ".join(f"{k}={v}" for k, v in filters.items() if v) or "none"
    by = Counter((f["verdict"], f["severity"]) for f in findings)
    out = [f"# {project} — Drift findings", "", provenance(project, snapshot), f"Filters: {flt}. {len(findings)} findings.", "",
           "## Summary", "", table(["Verdict", "Severity", "Count"], [[v, s, n] for (v, s), n in sorted(by.items())]), "",
           "## Findings", "", table(["Severity", "Verdict", "Status", "Finding", "Rule", "Subject", "Last seen"],
                                    [[f["severity"], f["verdict"], f["status"], f["title"], f["rule_id"], f["subject_key"], _date(f.get("last_seen"))]
                                     for f in findings]), ""]
    for f in findings[:500]:
        out += [f"### {f['title']}", "", f"* Rule: `{f['rule_id']}` v{f.get('rule_version', '')}", f"* Verdict: {f['verdict']} · severity {f['severity']} · status {f['status']}",
                f"* Subject: `{f['subject_key']}`", f"* First seen {_date(f.get('first_seen'))} · last seen {_date(f.get('last_seen'))} · {f.get('occurrences', 1)}×"]
        if f.get("resolution_note"):
            out.append(f"* Note: {f['resolution_note']}")
        out.append("")
        if f.get("expected") is not None or f.get("actual") is not None:
            out += ["Expected (baseline / declared) and actual (observed):", "", "```json",
                    json.dumps({"expected": f.get("expected"), "actual": f.get("actual")}, indent=2, default=str)[:4000], "```", ""]
        ev = f.get("evidence") or []
        if ev:
            out += ["Evidence:", ""] + [f"* {e.get('origin', '')} `{e.get('source_ref', '')}{':' + str(e['span']['line_start']) if (e.get('span') or {}).get('line_start') else ''}`"
                                         f" @ {(e.get('source_revision') or 'live')[:10]} ({e.get('parser_version', '')})" for e in ev[:10]] + [""]
    return "\n".join(out)


def _date(v: Any) -> str:
    return v.strftime("%Y-%m-%d") if isinstance(v, datetime) else str(v or "")[:10]


# ------------------------------------------------------------------ decisions & docs
def decisions_md(adrs_md: list[str], project: str, index: list[dict[str, Any]]) -> str:
    out = [f"# {project} — Decision records", "", provenance(project, None), "## Index", "",
           table(["#", "Title", "Status"], [[f"{a['number']:04d}", a["title"], a["status"]] for a in index]), ""]
    return "\n".join(out + [re.sub(r"^#", "##", md, flags=re.MULTILINE) for md in adrs_md])


def docs_md(docs: list[tuple[str, str]], project: str) -> str:
    out = [f"# {project} — Documentation", "", provenance(project, None)]
    for title, content in docs:
        out += [f"## {title}", "", re.sub(r"^(#+)", r"\1#", content, flags=re.MULTILINE), ""]
    return "\n".join(out)

"""Asynchronous and durable interactions in Python code: Temporal workflows/activities, PostgreSQL LISTEN/NOTIFY channels
and MCP tools — framework-level patterns, independent of any particular application.

These carry most of the behaviour of workflow-driven platforms (an API starts a durable workflow, a worker executes it,
activities call an LLM gateway or an MCP server, progress is pushed through NOTIFY to an SSE stream), yet none of it is an
HTTP route or a Kafka topic. Everything here is literal static evidence (decorators, call sites with literal names); a
name built entirely at run time is left out rather than guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

V_ASYNC = "py-async/1.0"

WF_DEF = re.compile(r"@workflow\.defn(?:\((?P<args>[^)]*)\))?\s*\n(?:\s*[@#][^\n]*\n)*\s*class\s+(?P<cls>\w+)")
ACT_DEF = re.compile(r"@activity\.defn(?:\((?P<args>[^)]*)\))?\s*\n(?:\s*[@#][^\n]*\n)*\s*(?:async\s+)?def\s+(?P<fn>\w+)")
NAME_ARG = re.compile(r"""name\s*=\s*["']([\w.\-]+)["']""")
WF_START = re.compile(r"""\.(?P<how>start_workflow|execute_workflow|signal_with_start_workflow|start_child_workflow|execute_child_workflow)\(\s*"""
                      r"""(?:["'](?P<lit>[\w.\-]+)["']|(?P<cls>[A-Z][a-z]\w*)(?:\.run)?\b|(?P<const>[A-Z_][A-Z0-9_]*)\b)""")
ACT_CALL = re.compile(r"""\.(?:execute_activity|start_activity|execute_local_activity|start_local_activity)(?:_method)?\(\s*"""
                      r"""(?:["'](?P<lit>[\w.\-]+)["']|(?:[A-Za-z_]\w*\.)*(?P<fn>[A-Za-z_]\w*))""")
WORKER_CTOR = re.compile(r"\bWorker\(\s*[^)]*?task_queue\s*=\s*(?:[\"'](?P<lit>[\w.\-]+)[\"']|(?P<const>[A-Za-z_][\w.]*))", re.DOTALL)

PG_NOTIFY = re.compile(r"pg_notify|\bNOTIFY\s+[A-Za-z_\"{:]", re.IGNORECASE)
PG_LISTEN = re.compile(r"add_listener\(|\bLISTEN\s+[A-Za-z_\"{:]", re.IGNORECASE)
DEF_WITH_PARAMS = re.compile(r"(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)")
CHANNEL_LIT = r"""(?P<f>f?)(?P<q>["'])(?P<ch>[A-Za-z_](?:[^"'\n{]|\{[^}\n]{0,60}\}){0,80})(?P=q)"""   # f"pg_{r['id'].hex}" too
DIRECT_NOTIFY = re.compile(r"""pg_notify\(\s*""" + CHANNEL_LIT, re.IGNORECASE)
DIRECT_LISTEN = re.compile(r"""add_listener\(\s*""" + CHANNEL_LIT)
SQL_NOTIFY = re.compile(r"""(?:execute|text|fetch|fetchval)\(\s*["'][^"'\n]*?\bNOTIFY\s+"?(?P<ch>[a-z_][a-z0-9_]*)""", re.IGNORECASE)
SQL_LISTEN = re.compile(r"""(?:execute|text)\(\s*["'][^"'\n]*?\bLISTEN\s+"?(?P<ch>[a-z_][a-z0-9_]*)""", re.IGNORECASE)

MCP_SERVER = re.compile(r"(\w+)\s*(?::\s*[\w.]+)?\s*=\s*(?:[\w.]+\.)?(?:FastMCP|MCPServer|McpServer|Server)\(")
MCP_TOOL = re.compile(r"""@(?P<var>\w+)\.tool\((?P<args>[^)]*)\)\s*\n(?:\s*[@#][^\n]*\n)*\s*(?:async\s+)?def\s+(?P<fn>\w+)""")
MCP_CLIENT = re.compile(r"\.call_tool\(|\bstreamablehttp_client\(|\bsse_client\(")


@dataclass
class ModuleAsync:
    workflows: dict[str, int] = field(default_factory=dict)          # workflow name -> line
    activities: dict[str, int] = field(default_factory=dict)         # activity name -> line
    starts: list[tuple[str, str, int]] = field(default_factory=list)  # (workflow name, how, line)
    activity_calls: list[tuple[str, int]] = field(default_factory=list)  # (activity name, line) executed from this module
    worker_queues: list[str] = field(default_factory=list)           # Worker(task_queue=...) constructed here
    notifies: list[tuple[str, int]] = field(default_factory=list)    # (channel pattern, line)
    listens: list[tuple[str, int]] = field(default_factory=list)
    mcp_tools: list[tuple[str, int]] = field(default_factory=list)
    mcp_client: bool = False
    mcp_client_lines: list[int] = field(default_factory=list)
    units: list[tuple[str, int, int]] = field(default_factory=list)  # top-level def/class: (name, first line, last line)
    unit_calls: dict[str, set[str]] = field(default_factory=dict)    # unit -> other top-level units it calls by name

    def unit_of(self, line: int) -> str | None:
        for name, a, b in self.units:
            if a <= line <= b:
                return name
        return None

    def closure(self, unit: str, depth: int = 2) -> set[str]:
        """The unit plus the module's own functions it calls (two levels): a route handler and its local helpers."""
        out, frontier = {unit}, {unit}
        for _ in range(depth):
            frontier = {c for u in frontier for c in self.unit_calls.get(u, ())} - out
            out |= frontier
        return out

    def closure_all(self, units: set[str]) -> set[str]:
        out: set[str] = set()
        for u in units:
            out |= self.closure(u)
        return out

    def within(self, units: set[str], items: list) -> list:
        """Items (tuples ending with a line number) found inside the given units."""
        return [it for it in items if self.unit_of(it[-1]) in units]

    def empty(self) -> bool:
        return not (self.workflows or self.activities or self.starts or self.activity_calls or self.worker_queues
                    or self.notifies or self.listens or self.mcp_tools or self.mcp_client)


def _line(src: str, pos: int) -> int:
    return src.count("\n", 0, pos) + 1


def channel_pattern(raw: str, is_f: bool) -> str | None:
    """`mission_{mid.hex}` -> `mission_*`; a name without a literal part is unknowable statically (None)."""
    pat = re.sub(r"\{[^}]*\}", "*", raw) if is_f else raw
    pat = re.sub(r"\*+", "*", pat).strip()
    if pat.endswith(("_", "-", ":", ".")):         # a literal prefix completed at run time ("mission_" + id)
        pat += "*"
    if not re.fullmatch(r"[A-Za-z_][\w*]{0,62}", pat) or not re.search(r"[A-Za-z]{2}", pat.replace("*", "")):
        return None
    return pat


def _const(name: str | None, consts: dict[str, str]) -> str | None:
    if not name:
        return None
    return consts.get(name) or consts.get(name.split(".")[-1])


@dataclass
class Wrappers:
    """Codebase-wide helpers wrapping pg_notify / LISTEN (e.g. `notify(conn, channel, payload)`, `hub.subscribe(channel)`),
    and channel-name factories (`def _channel(mid): return f"mission_{mid}"`)."""
    notify: dict[str, int] = field(default_factory=dict)     # function name -> index of the channel parameter
    listen: dict[str, int] = field(default_factory=dict)
    factories: dict[str, str] = field(default_factory=dict)  # function name -> channel pattern it returns


FACTORY = re.compile(r"""^\s*def\s+(\w+)\s*\([^)]*\)[^:\n]*:\s*\n(?:\s*(?:\"\"\"[^\n]*\"\"\"|#[^\n]*)\n)*\s*return\s+""" + CHANNEL_LIT, re.MULTILINE)


def _body(src: str, start: int, limit: int = 2500) -> str:
    body = src[start: start + limit]
    nxt = DEF_WITH_PARAMS.search(body)
    return body[: nxt.start()] if nxt else body


def find_wrappers(mods: dict[str, Any]) -> Wrappers:
    w = Wrappers()
    for m in mods.values():
        src = m.source
        if "return" in src and ("chan" in src or "notify" in src.lower() or "listen" in src.lower()):
            for fm in FACTORY.finditer(src):
                pat = channel_pattern(fm.group("ch"), bool(fm.group("f")))
                if pat and ("chan" in fm.group(1).lower() or "*" in pat):
                    w.factories[fm.group(1)] = pat
        has_notify, has_listen = bool(PG_NOTIFY.search(src)), bool(PG_LISTEN.search(src))
        if not (has_notify or has_listen):
            continue
        for d in DEF_WITH_PARAMS.finditer(src):
            params = [p.split(":")[0].split("=")[0].strip().lstrip("*") for p in d.group(2).split(",") if p.strip()]
            params = [p for p in params if p not in ("self", "cls")]
            idx = next((i for i, p in enumerate(params) if p in ("channel", "chan", "channel_name")), None)
            if idx is None:
                continue
            body = _body(src, d.end())
            if has_notify and PG_NOTIFY.search(body):
                w.notify[d.group(1)] = idx
            elif has_listen and (PG_LISTEN.search(body) or d.group(1) in ("subscribe", "listen")):
                w.listen[d.group(1)] = idx
    return w


def _split_args(src: str, start: int, limit: int = 400) -> list[str]:
    """Top-level comma-separated arguments of the call whose `(` ends at `start`."""
    depth, cur, args = 0, [], []
    for ch in src[start: start + limit]:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                args.append("".join(cur))
                return [a for a in args if a.strip()]
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    return []


def _wrapper_calls(src: str, names: dict[str, int], consts: dict[str, str], factories: dict[str, str] | None = None) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for name, idx in names.items():
        for m in re.finditer(rf"(?<![\w])(?:[A-Za-z_]\w*\.)?{re.escape(name)}\(", src):
            if src[max(0, m.start() - 4): m.start()] == "def ":
                continue
            args = _split_args(src, m.end())
            if idx >= len(args):
                continue
            a = args[idx].strip()
            if "=" in a and not a.startswith(("f'", 'f"', "'", '"')):
                a = a.split("=", 1)[1].strip()                          # channel=f"..."
            lit = re.fullmatch(CHANNEL_LIT, a)
            if lit:
                ch = channel_pattern(lit.group("ch"), bool(lit.group("f")))
            elif re.fullmatch(r"[A-Z_][A-Z0-9_]*", a):
                ch = channel_pattern(_const(a, consts) or "", False)
            elif (fc := re.match(r"(?:[A-Za-z_]\w*\.)?([A-Za-z_]\w*)\(", a)) and factories and fc.group(1) in factories:
                ch = factories[fc.group(1)]                              # notify(c, _channel(mid)) -> mission_*
            else:
                ch = None
            if ch:
                out.append((ch, _line(src, m.start())))
    return out


def analyze_module(mod: Any, wrappers: Wrappers) -> ModuleAsync:
    src, consts = mod.source, mod.consts
    r = ModuleAsync()
    if "workflow" in src or "activity" in src or "Worker(" in src:
        for m in WF_DEF.finditer(src):
            n = NAME_ARG.search(m.group("args") or "")
            r.workflows[n.group(1) if n else m.group("cls")] = _line(src, m.start("cls"))
        for m in ACT_DEF.finditer(src):
            n = NAME_ARG.search(m.group("args") or "")
            r.activities[n.group(1) if n else m.group("fn")] = _line(src, m.start("fn"))
        for m in WF_START.finditer(src):
            name = m.group("lit") or m.group("cls") or _const(m.group("const"), consts)
            if name:
                r.starts.append((name, m.group("how"), _line(src, m.start())))
        for m in ACT_CALL.finditer(src):
            r.activity_calls.append((m.group("lit") or m.group("fn"), _line(src, m.start())))
        for m in WORKER_CTOR.finditer(src):
            r.worker_queues.append(m.group("lit") or _const(m.group("const"), consts) or m.group("const") or "")
    if wrappers.notify:
        r.notifies += _wrapper_calls(src, wrappers.notify, consts, wrappers.factories)
    if wrappers.listen:
        r.listens += _wrapper_calls(src, wrappers.listen, consts, wrappers.factories)
    for rx, target in ((DIRECT_NOTIFY, r.notifies), (DIRECT_LISTEN, r.listens)):
        for m in rx.finditer(src):
            ch = channel_pattern(m.group("ch"), bool(m.group("f")))
            if ch:
                target.append((ch, _line(src, m.start())))
    for rx, target in ((SQL_NOTIFY, r.notifies), (SQL_LISTEN, r.listens)):
        for m in rx.finditer(src):
            target.append((m.group("ch"), _line(src, m.start())))
    servers = set(MCP_SERVER.findall(src)) if re.search(r"^\s*(?:from|import)\s+(?:fastmcp|mcp)\b", src, re.MULTILINE) else set()
    if servers:
        for m in MCP_TOOL.finditer(src):
            if m.group("var") in servers:
                n = NAME_ARG.search(m.group("args") or "")
                r.mcp_tools.append((n.group(1) if n else m.group("fn"), _line(src, m.start())))
    r.mcp_client_lines = [_line(src, m.start()) for m in MCP_CLIENT.finditer(src)] if "mcp" in src else []
    r.mcp_client = bool(r.mcp_client_lines)
    r.units = _units(src)
    if len(r.units) > 1:
        lines = src.splitlines()
        names = {u[0] for u in r.units}
        for name, a, b in r.units:
            body = "\n".join(lines[a:b])
            r.unit_calls[name] = {c for c in re.findall(r"(?<![\w.])([A-Za-z_]\w*)\(", body) if c in names and c != name}
    r.notifies = sorted(set(r.notifies))
    r.listens = sorted(set(r.listens))
    return r


UNIT = re.compile(r"^(?:async[ \t]+def|def|class)[ \t]+(\w+)", re.MULTILINE)


def _units(src: str) -> list[tuple[str, int, int]]:
    lines = src.splitlines()
    starts = []
    for m in UNIT.finditer(src):
        line = _line(src, m.start())
        while line > 1 and lines[line - 2].startswith(("@", "#")):  # decorators (and comments between them) belong to the unit
            line -= 1
        starts.append((m.group(1), line))
    total = src.count("\n") + 1
    out = []
    for i, (name, line) in enumerate(starts):
        # decorators above a unit belong to it; the unit ends where the next one (or its decorators) begins
        end = (starts[i + 1][1] - 1) if i + 1 < len(starts) else total
        out.append((name, line, end))
    return out


def analyze(mods: dict[str, Any]) -> dict[str, ModuleAsync]:
    w = find_wrappers(mods)
    out = {}
    for name, m in mods.items():
        a = analyze_module(m, w)
        if not a.empty():
            out[name] = a
    return out

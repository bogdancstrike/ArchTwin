"""Single-page web UIs inside a build context (React, Vue, Svelte, Angular) and the backend API paths they call.

A UI found in a service's build context becomes a `component` of that container ("Web UI"); each API path the UI calls
(string or template literal starting with /api or a configured prefix) is matched to the service's declared endpoints so
flows can start at the user, go through the UI and reach the right endpoint.

RPC-style UIs (one endpoint, the operation named in the body: `{action: "cases_list", payload}`) are recognized too:
* the transport — a file that POSTs (fetch/axios) to a URL from a build-time env var (`import.meta.env.VITE_APP_PRESENTER`)
  with an `action` in the body; the env var names the backend service (`presenter`), `.env*` files give the path;
* every action name sent through it — snake_case string literals passed to a caller (`sendToPresenter("cases_list")`,
  `presenterCall("…")`) or set as `action: "…"` — with the file and line, so each UI feature module calls
  `action:<name>@<service>`, resolved by the graph builder to the gateway's ACTION endpoint in any datasource.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

V_WEBUI = "web-ui/1.0"
FRAMEWORKS = [("next", "Next.js"), ("react", "React"), ("vue", "Vue"), ("svelte", "Svelte"), ("@angular/core", "Angular"), ("solid-js", "Solid")]
API_LITERAL = re.compile(r"""[`'"](/api/[A-Za-z0-9_\-/.{}$:?=&]*)""")
UI_EXT = {".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte"}


@dataclass
class RpcTransport:
    env: str                    # VITE_APP_PRESENTER
    service: str                # presenter
    path: str                   # /api/action (from .env files), "" when unknown
    file: str
    line: int


@dataclass
class RpcCall:
    action: str
    file: str
    line: int


@dataclass
class WebUi:
    root: Path
    framework: str
    name: str
    calls: dict[str, list[tuple[str, int]]] = field(default_factory=dict)      # normalized path -> [(file, line)]
    transports: list[RpcTransport] = field(default_factory=list)
    actions: list[RpcCall] = field(default_factory=list)


def find_uis(context: Path, files: list[Path], max_depth: int = 2) -> list[WebUi]:
    out = []
    for f in files:
        if f.name != "package.json" or "node_modules" in f.parts:
            continue
        try:
            rel = f.parent.relative_to(context)
        except ValueError:
            continue
        if len(rel.parts) > max_depth:
            continue
        try:
            pkg = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
        fw = next((label for dep, label in FRAMEWORKS if dep in deps), None)
        if fw:
            out.append(WebUi(f.parent, fw, str(pkg.get("name") or f.parent.name)))
    return out


def normalize(path: str) -> str:
    """'/api/jobs/${id}/cancel?x=1' -> '/api/jobs/{}/cancel' (template parts and query strings removed)."""
    p = path.split("?")[0]
    p = re.sub(r"\$\{[^}]*\}", "{}", p)
    p = re.sub(r"\{[^}/]*\}", "{}", p)
    return p.rstrip("/") or "/"


def scan_calls(ui: WebUi, files: list[Path]) -> WebUi:
    for f in files:
        if f.suffix not in UI_EXT or "node_modules" in f.parts or not str(f).startswith(str(ui.root) + "/"):
            continue
        if any(p in ("tests", "test", "__tests__", "e2e") for p in f.parts) or ".test." in f.name or ".spec." in f.name:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in API_LITERAL.finditer(text):
            ui.calls.setdefault(normalize(m.group(1)), []).append((str(f), text.count("\n", 0, m.start()) + 1))
    return ui


ENV_REF = re.compile(r"(?:import\.meta\.env|process\.env)\.([A-Z][A-Z0-9_]+)")
ACTION_NAME = r"([a-z][a-z0-9]*(?:_[a-z0-9]+)+)"
ACTION_LITERALS = (
    re.compile(rf"""\baction\s*:\s*['"`]{ACTION_NAME}['"`]"""),
    re.compile(rf"""\b[\w$]*(?:[Ss]end|[Cc]all|[Pp]resenter|[Aa]ction|[Rr]pc|[Ii]nvoke|[Dd]ispatch)[\w$]*\s*(?:<[^>()]*>)?\(\s*['"`]{ACTION_NAME}['"`]"""),
)
CONST_VALUE = re.compile(rf"""(?:^|[{{,\s])([\w$]+)\s*[:=]\s*['"`]{ACTION_NAME}['"`]""", re.MULTILINE)
CALL_BY_NAME = re.compile(r"""\b[\w$]*(?:[Ss]end|[Cc]all|[Pp]resenter|[Rr]pc|[Ii]nvoke)[\w$]*\s*\(\s*(?:[\w$]+(?:\.|\[['"]))?([\w$]+)['"\]]*\s*[,)]""")
RPC_MODULE = re.compile(r"action|endpoint|api|service|presenter|transport|rpc|command", re.IGNORECASE)
SENDS = re.compile(r"\bfetch\s*\(|\baxios\b|\.post\s*\(")
ENV_LINE = re.compile(r"^\s*([A-Z][A-Z0-9_]+)\s*=\s*['\"]?([^'\"\s#]+)", re.MULTILINE)


def _skip(f: Path) -> bool:
    return (any(p in ("tests", "test", "__tests__", "e2e", "node_modules", "dist", "coverage") for p in f.parts)
            or ".test." in f.name or ".spec." in f.name or ".stories." in f.name)


def env_values(root: Path) -> dict[str, str]:
    """Build-time env values from `.env*` files (first non-localhost value wins: production-like paths)."""
    out: dict[str, str] = {}
    for f in sorted(root.glob(".env*")):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for k, v in ENV_LINE.findall(text):
            if k not in out or "localhost" in out[k]:
                out[k] = v
    return out


def scan_rpc(ui: WebUi, files: list[Path]) -> WebUi:
    """Find the RPC transport(s) and every action the UI sends (see module docstring)."""
    from archtwin.connectors.analyzers.python_code import service_from_variable
    env = env_values(ui.root)
    texts: list[tuple[Path, str]] = []
    for f in files:
        if f.suffix not in UI_EXT or not str(f).startswith(str(ui.root) + "/") or _skip(f):
            continue
        try:
            texts.append((f, f.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    seen_env: set[str] = set()
    for f, text in texts:
        if not SENDS.search(text) or not re.search(r"\baction\b", text):
            continue
        for m in ENV_REF.finditer(text):
            var = m.group(1)
            service = service_from_variable(var)
            if var in seen_env or not service:
                continue
            seen_env.add(var)
            url = env.get(var, "")
            path = re.sub(r"^[a-z]+://[^/]+", "", url) if url else ""
            ui.transports.append(RpcTransport(var, service, path.split("?")[0], str(f), text.count("\n", 0, m.start()) + 1))
    if not ui.transports:
        return ui
    consts: dict[str, list[tuple[str, Path, int]]] = {}       # constant name -> [(action, defining file, line)]
    for f, text in texts:
        if RPC_MODULE.search(f.stem) or RPC_MODULE.search(f.parent.name):    # action-name constant maps (list: "cases_list")
            for m in CONST_VALUE.finditer(text):
                consts.setdefault(m.group(1), []).append((m.group(2), f, text.count("\n", 0, m.start(2)) + 1))
    used: set[tuple[str, Path]] = set()
    for f, text in texts:
        found: set[tuple[str, int]] = set()
        for rx in ACTION_LITERALS:
            for m in rx.finditer(text):
                found.add((m.group(1), text.count("\n", 0, m.start()) + 1))
        for m in CALL_BY_NAME.finditer(text):                 # sendToPresenter(config_endpoints.CREATE_SOURCE, …): the USE site
            for action, df, _ in consts.get(m.group(1), []):
                found.add((action, text.count("\n", 0, m.start()) + 1))
                used.add((action, df))
        ui.actions += [RpcCall(a, str(f), line) for a, line in sorted(found)]
    for defs in consts.values():                         # constants whose use site is not a direct call (passed around)
        for action, df, line in defs:
            if (action, df) not in used and not any(a.action == action for a in ui.actions):
                ui.actions.append(RpcCall(action, str(df), line))
    return ui


def primary_transport(ui: WebUi) -> RpcTransport | None:
    """The JSON action endpoint (an upload variant like *_UPLOAD carries the same actions as multipart)."""
    ts = sorted(ui.transports, key=lambda t: ("UPLOAD" in t.env or "FILE" in t.env, len(t.env)))
    return ts[0] if ts else None


def match_endpoints(call: str, endpoints: dict[str, list[str]]) -> list[str]:
    """Endpoint keys a UI call path reaches: every method on the exact path, else the shortest longer path it prefixes.
    (The HTTP method of a call site is not resolved statically, so all methods on the path are linked.)"""
    if call in endpoints:
        return endpoints[call]
    best = None
    for norm in endpoints:
        if norm.startswith(call + "/") and (best is None or len(norm) < len(best)):
            best = norm
    return endpoints[best] if best else []

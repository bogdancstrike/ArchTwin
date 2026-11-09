"""Declarative APIs and gateway routing tables (configuration files that define endpoints or route requests elsewhere).

* Declared endpoints — JSON like {"namespaces": [...], "endpoints": [{"namespace", "operation_name", "request_method",
  "exec_method": {"module_name", "method_name"}}]} (Flask-RESTX style generators): path `/{namespace}/{operation_name}`,
  handled by `module_name.method_name` (which also makes the handler module reachable for code analysis).
* Routing tables — a JSON object whose entries look like {"service": "host:port", "endpoint": "/path", "method": "post"}:
  an API gateway / BFF dispatching an action to a backend service. Each route becomes an action handled by the gateway
  and a call to `name:<host>#<METHOD> <path>`, resolved by the graph builder to the backend's endpoint in any datasource.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

V_DECLARED = "declared-endpoints/1.0"
V_ROUTES = "gateway-routes/1.0"
HOST_KEYS = ("service", "host", "upstream", "target", "url", "base_url")
PATH_KEYS = ("endpoint", "path", "route", "uri")
MAX_JSON = 2_000_000


@dataclass
class DeclaredEndpoint:
    method: str
    path: str
    module: str
    handler: str
    source: str
    line: int


@dataclass
class Route:
    action: str
    host: str
    path: str
    method: str
    source: str
    line: int
    roles: list[str] = field(default_factory=list)
    description: str = ""


def _json_files(root: Path, files: list[Path]) -> list[tuple[Path, str, object]]:
    out = []
    for f in files:
        if f.suffix != ".json" or f.name in ("package.json", "package-lock.json", "tsconfig.json") or f.stat().st_size > MAX_JSON:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            out.append((f, text, json.loads(text)))
        except (OSError, ValueError):
            continue
    return out


def _line(text: str, needle: str) -> int:
    i = text.find(needle)
    return text.count("\n", 0, i) + 1 if i >= 0 else 1


def declared_endpoints(root: Path, files: list[Path]) -> list[DeclaredEndpoint]:
    out = []
    for f, text, data in _json_files(root, files):
        if not isinstance(data, dict) or not isinstance(data.get("endpoints"), list) or "namespaces" not in data:
            continue
        rel = str(f.relative_to(root))
        for e in data["endpoints"]:
            if not isinstance(e, dict) or not e.get("operation_name"):
                continue
            ex = e.get("exec_method") or {}
            methods = e.get("request_method") or ["get"]
            for m in methods if isinstance(methods, list) else [methods]:
                out.append(DeclaredEndpoint(str(m).upper(), f"/{e.get('namespace', '').strip('/')}/{e['operation_name']}".replace("//", "/"),
                                            str(ex.get("module_name") or ""), str(ex.get("method_name") or ""), rel,
                                            _line(text, f'"{e["operation_name"]}"')))
    return out


def _route_value(v: dict, keys: tuple[str, ...]) -> str:
    return next((str(v[k]) for k in keys if isinstance(v.get(k), str) and v.get(k)), "")


def routing_tables(root: Path, files: list[Path]) -> list[Route]:
    out = []
    for f, text, data in _json_files(root, files):
        if not isinstance(data, dict):
            continue
        entries = {k: v for k, v in data.items() if isinstance(v, dict) and _route_value(v, HOST_KEYS) and _route_value(v, PATH_KEYS)}
        if len(entries) < 2:
            continue
        rel = str(f.relative_to(root))
        for action, v in entries.items():
            host = _route_value(v, HOST_KEYS)
            host = re.sub(r"^https?://", "", host).split("/")[0]
            audit = v.get("audit") if isinstance(v.get("audit"), dict) else {}
            out.append(Route(action, host, _route_value(v, PATH_KEYS), str(v.get("method") or "post").upper(), rel, _line(text, f'"{action}"'),
                             [str(r) for r in v.get("roles") or []][:10], str(audit.get("description") or audit.get("display_name") or "")[:200]))
    return out


def host_name(host: str) -> str | None:
    """'qsint-data-query:8080' -> 'qsint-data-query'; local hosts and IPs are not services."""
    h = host.split(":")[0].lower()
    if not h or h in ("localhost", "127.0.0.1", "0.0.0.0") or re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", h):
        return None
    return h

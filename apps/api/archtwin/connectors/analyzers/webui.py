"""Single-page web UIs inside a build context (React, Vue, Svelte, Angular) and the backend API paths they call.

A UI found in a service's build context becomes a `component` of that container ("Web UI"); each API path the UI calls
(string or template literal starting with /api or a configured prefix) is matched to the service's declared endpoints so
flows can start at the user, go through the UI and reach the right endpoint.
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
class WebUi:
    root: Path
    framework: str
    name: str
    calls: dict[str, list[tuple[str, int]]] = field(default_factory=dict)      # normalized path -> [(file, line)]


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

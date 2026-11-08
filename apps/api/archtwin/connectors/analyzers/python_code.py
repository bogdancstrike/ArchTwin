"""tree-sitter based Python analysis: module index, import graph, FastAPI/Flask-style routes (parser_version below)."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from tree_sitter_language_pack import get_parser

PARSER_VERSION = "py-treesitter/1.0"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "websocket", "api_route", "route"}


@lru_cache
def _parser():
    return get_parser("python")


@dataclass
class Route:
    method: str
    path: str
    file: str
    line: int
    handler: str


@dataclass
class PyModule:
    name: str
    path: Path
    imports: set[str] = field(default_factory=set)
    routes: list[Route] = field(default_factory=list)


def module_index(context_dir: Path, files: list[Path]) -> dict[str, Path]:
    """Map dotted module names to files for packages rooted directly under the build context (or context/src)."""
    idx: dict[str, Path] = {}
    for base in (context_dir, context_dir / "src"):
        for f in files:
            if f.suffix != ".py":
                continue
            try:
                rel = f.relative_to(base)
            except ValueError:
                continue
            parts = list(rel.with_suffix("").parts)
            if not parts or any(p.startswith(".") or "-" in p for p in parts):
                continue
            # only count it as a package module if every parent directory is a package
            if len(parts) > 1 and not all((base.joinpath(*parts[:i]) / "__init__.py").exists() for i in range(1, len(parts))):
                continue
            if parts[-1] == "__init__":
                parts = parts[:-1]
            if parts:
                idx.setdefault(".".join(parts), f)
    return idx


def _text(n) -> str:
    return n.text.decode("utf-8", "replace")


def _string_value(n) -> str | None:
    if n.type != "string":
        return None
    return "".join(_text(c) for c in n.children if c.type == "string_content")


def parse_module(name: str, path: Path, is_pkg: bool) -> PyModule:
    src = path.read_bytes()
    tree = _parser().parse(src)
    mod = PyModule(name, path)
    prefixes: dict[str, str] = {}

    def resolve_relative(level: int, rest: str) -> str:
        base = name.split(".") if is_pkg else name.split(".")[:-1]
        base = base[: len(base) - (level - 1)] if level > 1 else base
        return ".".join([*base, rest] if rest else base)

    stack = [tree.root_node]
    while stack:
        n = stack.pop()
        t = n.type
        if t == "import_statement":
            for c in n.children:
                if c.type == "dotted_name":
                    mod.imports.add(_text(c))
                elif c.type == "aliased_import":
                    mod.imports.add(_text(c.children[0]))
        elif t == "import_from_statement":
            target = n.child_by_field_name("module_name")
            names = [c for c in n.children_by_field_name("name")]
            if target is not None and target.type == "relative_import":
                level = sum(len(_text(c)) for c in target.children if c.type == "import_prefix")
                rest = "".join(_text(c) for c in target.children if c.type == "dotted_name")
                base = resolve_relative(level, rest)
            elif target is not None:
                base = _text(target)
            else:
                base = ""
            if base:
                mod.imports.add(base)
                for nm in names:
                    nn = nm.children[0] if nm.type == "aliased_import" else nm
                    mod.imports.add(f"{base}.{_text(nn)}")
        elif t == "assignment":
            # router = APIRouter(prefix="/api/v1/x")
            left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
            if left is not None and right is not None and right.type == "call":
                fn = _text(right.child_by_field_name("function") or right)
                if fn.endswith(("APIRouter", "Blueprint", "FastAPI")):
                    args = right.child_by_field_name("arguments")
                    for a in (args.children if args is not None else []):
                        if a.type == "keyword_argument" and _text(a.child_by_field_name("name")) in ("prefix", "url_prefix"):
                            v = _string_value(a.child_by_field_name("value"))
                            if v is not None:
                                prefixes[_text(left)] = v
        elif t == "decorator":
            call = next((c for c in n.children if c.type == "call"), None)
            if call is not None:
                fn = call.child_by_field_name("function")
                if fn is not None and fn.type == "attribute":
                    obj, attr = fn.child_by_field_name("object"), fn.child_by_field_name("attribute")
                    meth = _text(attr) if attr is not None else ""
                    if meth in HTTP_METHODS:
                        args = call.child_by_field_name("arguments")
                        first = next((c for c in (args.children if args is not None else []) if c.type == "string"), None)
                        p = _string_value(first) if first is not None else None
                        if p is not None and (p.startswith("/") or p == ""):
                            handler = ""
                            parent = n.parent
                            if parent is not None:
                                d = parent.child_by_field_name("definition")
                                if d is not None and d.child_by_field_name("name") is not None:
                                    handler = _text(d.child_by_field_name("name"))
                            m = "GET" if meth in ("route", "api_route") else ("WS" if meth == "websocket" else meth.upper())
                            mod.routes.append(Route(m, (_text(obj) if obj is not None else "", p), str(path), n.start_point[0] + 1, handler))  # type: ignore[arg-type]
        stack.extend(n.children)
    # apply router prefixes
    fixed = []
    for r in mod.routes:
        objname, p = r.path  # type: ignore[misc]
        fixed.append(Route(r.method, (prefixes.get(objname, "") + p) or "/", r.file, r.line, r.handler))
    mod.routes = sorted(fixed, key=lambda r: (r.line, r.method))
    return mod


def analyze(context_dir: Path, files: list[Path]) -> dict[str, PyModule]:
    idx = module_index(context_dir, files)
    out = {}
    for name, path in idx.items():
        try:
            out[name] = parse_module(name, path, path.name == "__init__.py")
        except Exception:  # noqa: BLE001 — a broken file never aborts the scan (partial evidence is still evidence)
            continue
    # keep only imports that resolve to modules in this codebase (prefix match)
    names = set(out)
    for m in out.values():
        resolved = set()
        for imp in m.imports:
            cand = imp
            while cand and cand not in names:
                cand = cand.rpartition(".")[0]
            if cand:
                resolved.add(cand)
        m.imports = resolved - {m.name}
    return out


def reachable(mods: dict[str, PyModule], entries: list[str]) -> set[str]:
    seen: set[str] = set()
    todo = [e for e in entries if e in mods]
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        seen.add(m)
        # importing a.b.c also executes a and a.b
        parts = m.split(".")
        for i in range(1, len(parts)):
            p = ".".join(parts[:i])
            if p in mods and p not in seen:
                todo.append(p)
        todo.extend(i for i in mods[m].imports if i not in seen)
    return seen


def component_of(module: str, depth: int = 2) -> str:
    return ".".join(module.split(".")[:depth])

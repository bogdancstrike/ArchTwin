"""tree-sitter based Python analysis: module index, import graph, FastAPI/Flask-style routes (parser_version below)."""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_python
from tree_sitter import Language, Parser

PARSER_VERSION = "py-treesitter/1.2"     # 1.2: L4 code elements (classes, functions, references)
KAFKA_PRODUCE = {"produce", "send", "send_and_wait"}
KAFKA_CLIENTS = {"Producer", "Consumer", "KafkaProducer", "KafkaConsumer", "AIOKafkaProducer", "AIOKafkaConsumer",
                 "SerializingProducer", "DeserializingConsumer"}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "websocket", "api_route", "route"}


# Grammar ships compiled inside the official `tree-sitter-python` wheel: nothing is downloaded at runtime.
PY_LANGUAGE = Language(tree_sitter_python.language())
_local = threading.local()


def _parser():
    """One parser per thread: tree-sitter parsers are not thread-safe and scans run concurrently in worker threads."""
    p = getattr(_local, "parser", None)
    if p is None:
        p = _local.parser = Parser(PY_LANGUAGE)
    return p


@dataclass
class Route:
    method: str
    path: str
    file: str
    line: int
    handler: str


@dataclass
class KafkaUse:
    direction: str          # "publishes" | "consumes"
    topic: str
    line: int
    group: str = ""


@dataclass
class CodeDef:
    """A top-level class or function (C4 L4 code element) with the names its body references."""
    name: str
    kind: str                       # class | function
    line_start: int
    line_end: int
    bases: list[str] = field(default_factory=list)
    refs: set[str] = field(default_factory=set)
    methods: int = 0
    is_async: bool = False
    method_list: list[tuple[str, int]] = field(default_factory=list)     # (name, line) of methods, for L4 detail


@dataclass
class PyModule:
    name: str
    path: Path
    imports: set[str] = field(default_factory=set)
    names: dict[str, str] = field(default_factory=dict)     # local name -> fully qualified imported name
    external_imports: set[str] = field(default_factory=set)  # third-party / stdlib imports (resources: openai, sqlite3, ...)
    consts: dict[str, str] = field(default_factory=dict)      # module-level string constants (API_PREFIX = "/api/x")
    prefixes: dict[str, str] = field(default_factory=dict)    # router variable -> URL prefix
    router_calls: dict[str, tuple[str, list[str]]] = field(default_factory=dict)       # var = factory("...") (resolved later)
    router_factories: dict[str, tuple[list[tuple[str, str]], str]] = field(default_factory=dict)   # fn -> (params, template)
    raw_routes: list[tuple[str, str, str, str, int, str]] = field(default_factory=list)  # (method, router var, path, file, line, handler)
    source: str = ""
    defs: list[CodeDef] = field(default_factory=list)
    routes: list[Route] = field(default_factory=list)
    kafka: list[KafkaUse] = field(default_factory=list)
    uses_kafka_client: bool = False


NOT_PACKAGES = {"tests", "test", "docs", "doc", "examples", "example", "scripts", "tools", "venv", "env", "build", "dist", "node_modules"}


def _is_package_dir(d: Path) -> bool:
    return (d / "__init__.py").exists() or (d.name.isidentifier() and d.name not in NOT_PACKAGES)


def package_roots(context_dir: Path, files: list[Path], entries: list[str] | None = None, copied: list[str] | None = None) -> list[Path]:
    """Directories Python modules are imported from: the build context, context/src, directories the Dockerfile copies
    into the working directory (`COPY backend/ ./`), and any directory (depth <= 2) holding the entry module's package."""
    roots = [context_dir, context_dir / "src"]
    for c in copied or []:
        d = (context_dir / c).resolve()
        if d.is_dir() and str(d).startswith(str(context_dir.resolve())):
            roots.append(d)
    tops = {e.split(".")[0] for e in entries or []}
    for f in files:
        if f.name != "__init__.py":
            continue
        try:
            rel = f.parent.relative_to(context_dir)
        except ValueError:
            continue
        if 1 <= len(rel.parts) <= 3 and rel.parts[-1] in tops:
            roots.append(f.parent.parent)
    seen, out = set(), []
    for r in roots:
        k = str(r.resolve())
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def module_index(context_dir: Path, files: list[Path], roots: list[Path] | None = None) -> dict[str, Path]:
    """Map dotted module names to files for packages rooted under the given roots (default: context, context/src)."""
    idx: dict[str, Path] = {}
    for base in roots or [context_dir, context_dir / "src"]:
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
            # every parent directory must be a package: a regular one (__init__.py) or an implicit namespace package
            # (PEP 420: a plain directory with an identifier name that is not a test/tooling folder)
            if len(parts) > 1 and not all(_is_package_dir(base.joinpath(*parts[:i])) for i in range(1, len(parts))):
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


def _template(n, consts: dict[str, str]) -> str | None:
    """A string or f-string as a template: constants substituted, other interpolations kept as {name}."""
    if n is None or n.type != "string":
        return None
    out = []
    for c in n.children:
        if c.type == "string_content":
            out.append(_text(c))
        elif c.type == "interpolation":
            expr = next((x for x in c.children if x.type not in ("{", "}")), None)
            name = _text(expr) if expr is not None else ""
            out.append(consts.get(name, "{" + name + "}"))
    return "".join(out)


def _router_prefix(call, consts: dict[str, str]) -> str | None:
    args = call.child_by_field_name("arguments")
    for a in (args.children if args is not None else []):
        if a.type == "keyword_argument" and _text(a.child_by_field_name("name")) in ("prefix", "url_prefix"):
            return _template(a.child_by_field_name("value"), consts)
    return None


def _router_factories(root, consts: dict[str, str]) -> dict[str, tuple[list[tuple[str, str]], str]]:
    """Module-level functions returning APIRouter/Blueprint(prefix=...): fn -> ([(param, default)], prefix template)."""
    out = {}
    for top in root.children:
        d = top.child_by_field_name("definition") if top.type == "decorated_definition" else top
        if d is None or d.type != "function_definition":
            continue
        stack, prefix = [d.child_by_field_name("body")], None
        while stack and prefix is None:
            x = stack.pop()
            if x is None:
                continue
            if x.type == "call" and _text(x.child_by_field_name("function") or x).endswith(("APIRouter", "Blueprint")):
                prefix = _router_prefix(x, consts)
            stack.extend(x.children)
        if prefix is None:
            continue
        params = []
        for prm in (d.child_by_field_name("parameters").children if d.child_by_field_name("parameters") is not None else []):
            if prm.type == "identifier":
                params.append((_text(prm), ""))
            elif prm.type in ("default_parameter", "typed_default_parameter"):
                params.append((_text(prm.child_by_field_name("name")), _string_value(prm.child_by_field_name("value")) or ""))
            elif prm.type == "typed_parameter":
                params.append((_text(prm.children[0]), ""))
        out[_text(d.child_by_field_name("name"))] = (params, prefix)
    return out


def _apply_factory(factory: tuple[list[tuple[str, str]], str], args: list[str]) -> str:
    params, template = factory
    values = {name: (args[i] if i < len(args) else default) for i, (name, default) in enumerate(params)}
    return re.sub(r"\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), template)


def _strings(n) -> list[str]:
    """String literals of a node that is a string or a list/tuple of strings."""
    if n is None:
        return []
    if n.type == "string":
        v = _string_value(n)
        return [v] if v else []
    if n.type in ("list", "tuple"):
        return [v for c in n.children if c.type == "string" and (v := _string_value(c))]
    return []


def _kafka_call(n, mod: PyModule) -> None:
    """Deterministic Kafka producer/consumer detection (confluent-kafka, kafka-python, aiokafka): literal topic names only.

    produce("t") / send("t") / send_and_wait("t") on a Kafka client -> publishes; subscribe(["t"]) or KafkaConsumer("t") ->
    consumes; `group.id` / group_id literals give the consumer group. Dynamic topic names are not guessed.
    """
    fn = n.child_by_field_name("function")
    args = n.child_by_field_name("arguments")
    if fn is None or args is None:
        return
    argv = [c for c in args.children if c.type not in ("(", ")", ",")]
    line = n.start_point[0] + 1
    name = _text(fn).rsplit(".", 1)[-1]
    if name in KAFKA_CLIENTS:
        mod.uses_kafka_client = True
        for a in argv:      # group id from config dict or keyword
            if a.type == "dictionary":
                for pair in a.children:
                    if pair.type == "pair" and _string_value(pair.child_by_field_name("key")) == "group.id":
                        mod.kafka.append(KafkaUse("group", _string_value(pair.child_by_field_name("value")) or "", line))
            elif a.type == "keyword_argument" and _text(a.child_by_field_name("name")) == "group_id":
                v = _string_value(a.child_by_field_name("value"))
                if v:
                    mod.kafka.append(KafkaUse("group", v, line))
        if name.endswith("Consumer"):
            for a in argv:
                if a.type == "string" and (v := _string_value(a)):
                    mod.kafka.append(KafkaUse("consumes", v, line))
        return
    if fn.type != "attribute" or not argv:
        return
    if name in KAFKA_PRODUCE:
        first = argv[0] if argv[0].type == "string" else next((a.child_by_field_name("value") for a in argv if a.type == "keyword_argument"
                                                               and _text(a.child_by_field_name("name")) == "topic"), None)
        for v in _strings(first):
            mod.kafka.append(KafkaUse("publishes", v, line))
    elif name == "subscribe":
        for v in _strings(argv[0]):
            mod.kafka.append(KafkaUse("consumes", v, line))


MAX_REFS = 200
DYNAMIC_REF = re.compile(r"""["']([A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)+):[A-Za-z_]\w*["']""")
IMPORT_MODULE = re.compile(r"""import_module\(\s*["']([A-Za-z_][\w.]*)["']""")


def _idents(node, out: set[str]) -> None:
    stack = [node]
    while stack and len(out) < MAX_REFS:
        n = stack.pop()
        if n.type == "identifier":
            out.add(_text(n))
        elif n.type == "attribute":                       # a.b.c -> "a" (the imported module or object)
            obj = n.child_by_field_name("object")
            if obj is not None and obj.type == "identifier":
                out.add(_text(obj))
        stack.extend(n.children)


def _code_defs(root) -> list[CodeDef]:
    """Top-level classes and functions of a module (L4), with line span, base classes and referenced names."""
    out: list[CodeDef] = []
    for top in root.children:
        d = top.child_by_field_name("definition") if top.type == "decorated_definition" else top
        if d is None or d.type not in ("class_definition", "function_definition"):
            continue
        nm = d.child_by_field_name("name")
        if nm is None:
            continue
        cd = CodeDef(_text(nm), "class" if d.type == "class_definition" else "function", top.start_point[0] + 1, d.end_point[0] + 1,
                     is_async=d.type == "function_definition" and _text(d).startswith("async"))
        if d.type == "class_definition":
            sup = d.child_by_field_name("superclasses")
            for c in (sup.children if sup is not None else []):
                if c.type in ("identifier", "attribute"):
                    cd.bases.append(_text(c))
            body = d.child_by_field_name("body")
            for c in (body.children if body is not None else []):
                fd = c.child_by_field_name("definition") if c.type == "decorated_definition" else c
                if fd is not None and fd.type == "function_definition" and fd.child_by_field_name("name") is not None:
                    cd.method_list.append((_text(fd.child_by_field_name("name")), c.start_point[0] + 1))
            cd.methods = len(cd.method_list)
        body = d.child_by_field_name("body")
        if body is not None:
            _idents(body, cd.refs)
        params = d.child_by_field_name("parameters")
        if params is not None:
            _idents(params, cd.refs)                      # type annotations name other classes
        rt = d.child_by_field_name("return_type")
        if rt is not None:
            _idents(rt, cd.refs)
        cd.refs.update(b.split(".")[0] if "." in b else b for b in cd.bases)          # a base class is a reference too
        cd.refs.discard(cd.name)
        out.append(cd)
    return out


def parse_module(name: str, path: Path, is_pkg: bool) -> PyModule:
    src = path.read_bytes()
    tree = _parser().parse(src)
    mod = PyModule(name, path, source=src.decode("utf-8", "replace")[:400_000])
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
                    alias = nm.child_by_field_name("alias") if nm.type == "aliased_import" else None
                    mod.imports.add(f"{base}.{_text(nn)}")
                    mod.names[_text(alias) if alias is not None else _text(nn).split(".")[-1]] = f"{base}.{_text(nn)}"
        elif t == "assignment":
            left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
            if left is not None and right is not None and left.type == "identifier" and right.type == "string" and n.parent is not None \
                    and n.parent.parent is not None and n.parent.parent.type == "module":
                v = _string_value(right)                                 # API_PREFIX = "/api/investigations"
                if v is not None and "{" not in _text(right)[:3]:
                    mod.consts[_text(left)] = v
            if left is not None and right is not None and right.type == "call":
                fn = _text(right.child_by_field_name("function") or right)
                if fn.endswith(("APIRouter", "Blueprint", "FastAPI")):    # router = APIRouter(prefix="/api/v1/x" | f"{API}/x")
                    v = _router_prefix(right, mod.consts)
                    if v is not None:
                        prefixes[_text(left)] = v
                else:                                                    # router = investigation_router("/{case_id}") (resolved later)
                    args = right.child_by_field_name("arguments")
                    lits = [_string_value(a) or "" for a in (args.children if args is not None else []) if a.type == "string"]
                    mod.router_calls[_text(left)] = (fn, lits)
        elif t == "call":
            _kafka_call(n, mod)
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
    mod.defs = _code_defs(tree.root_node)
    # dynamic imports (plugin registries, app factories): "pkg.mod:Attr" strings and import_module("pkg.mod")
    mod.imports |= {m.group(1) for m in DYNAMIC_REF.finditer(mod.source)}
    mod.imports |= {m.group(1) for m in IMPORT_MODULE.finditer(mod.source)}
    mod.router_factories = _router_factories(tree.root_node, mod.consts)
    mod.prefixes = prefixes
    mod.raw_routes = [(r.method, r.path[0], r.path[1], r.file, r.line, r.handler) for r in mod.routes]  # type: ignore[index]
    _finalize_routes(mod)
    return mod


def _finalize_routes(mod: PyModule) -> None:
    mod.routes = sorted((Route(m, (mod.prefixes.get(var, "") + p) or "/", f, line, h) for m, var, p, f, line, h in mod.raw_routes),
                        key=lambda r: (r.line, r.method))


def resolve_router_prefixes(mods: dict[str, PyModule]) -> None:
    """Prefixes produced by router factories defined in other modules (`router = investigation_router("/{case_id}")`)."""
    for m in mods.values():
        changed = False
        for var, (fn, args) in m.router_calls.items():
            name = fn.split(".")[-1]
            factory = m.router_factories.get(name)
            if factory is None:
                target = m.names.get(fn) or m.names.get(name)
                owner = mods.get(target.rpartition(".")[0]) if target else None
                factory = owner.router_factories.get(name) if owner else None
            if factory is not None and var not in m.prefixes:
                m.prefixes[var] = _apply_factory(factory, args)
                changed = True
        if changed:
            _finalize_routes(m)


def analyze(context_dir: Path, files: list[Path], errors: list[str] | None = None, roots: list[Path] | None = None) -> dict[str, PyModule]:
    idx = module_index(context_dir, files, roots)
    out = {}
    for name, path in idx.items():
        try:
            out[name] = parse_module(name, path, path.name == "__init__.py")
        except Exception as e:  # noqa: BLE001 — a broken file never aborts the scan, but it is reported (never silent)
            if errors is not None:
                errors.append(f"{path.name}: {type(e).__name__}: {str(e)[:120]}")
            continue
    resolve_router_prefixes(out)
    # keep only imports that resolve to modules in this codebase (prefix match); the rest are kept as external imports
    names = set(out)
    tops = {n.split(".")[0] for n in names}
    for m in out.values():
        m.external_imports = {i for i in m.imports if i.split(".")[0] not in tops}
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


APP_REF = re.compile(r"""["']([A-Za-z_][\w.]*):[A-Za-z_]\w*["']""")
CONST_APP_REF = re.compile(r"""^([A-Z_][A-Z0-9_]*)\s*(?::[^=]+)?=\s*["']([A-Za-z_][\w.]*):[A-Za-z_]\w*["']""", re.MULTILINE)


def _function_block(src: str, name: str) -> str | None:
    m = re.search(rf"^([ \t]*)(?:async[ \t]+)?def[ \t]+{re.escape(name)}[ \t]*\(", src, re.MULTILINE)
    if not m:
        return None
    indent = len(m.group(1))
    lines = src[m.start():].splitlines()
    block = [lines[0]]
    for ln in lines[1:]:
        if ln.strip() and not ln.strip().startswith("#") and len(ln) - len(ln.lstrip()) <= indent and not ln.lstrip().startswith((")", "]")):
            break
        block.append(ln)
    return "\n".join(block)


def role_entries(mods: dict[str, PyModule], script_module: str, command: str) -> list[str]:
    """Modules a CLI role runs: `service-data query` -> the `query` command function in the script's package -> what it
    imports, the "module:attr" app strings it uses (directly or via module constants such as QUERY_APP)."""
    func = command.replace("-", "_")
    package = script_module if any(m.startswith(script_module + ".") for m in mods) else script_module.rpartition(".")[0]
    names = set(mods)
    found: set[str] = set()
    for m in sorted(x for x in mods if x == script_module or x.startswith(package + ".")):
        src = mods[m].source
        block = _function_block(src, func)
        if block is None:
            continue
        refs = re.findall(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import", block, re.MULTILINE)
        refs += re.findall(r"^\s*import\s+([A-Za-z_][\w.]*)", block, re.MULTILINE)
        refs += APP_REF.findall(block)
        refs += [mod for const, mod in CONST_APP_REF.findall(src) if re.search(rf"\b{const}\b", block)]
        for ref in refs:
            cand = ref
            while cand and cand not in names:
                cand = cand.rpartition(".")[0]
            if cand and cand != m:
                found.add(cand)
    return sorted(found)


SERVER_CALL = re.compile(r"\b(?:uvicorn|gunicorn|hypercorn|granian|waitress|daphne)\b|\bserve\s*\(|\.run_app\s*\(|app\.run\s*\(")


def role_starts_server(mods: dict[str, PyModule], script_module: str, command: str) -> bool:
    """Whether a CLI role's command function starts an HTTP server (uvicorn.run, serve(...), app.run, …)."""
    package = script_module if any(m.startswith(script_module + ".") for m in mods) else script_module.rpartition(".")[0]
    for m in sorted(x for x in mods if x == script_module or x.startswith(package + ".")):
        block = _function_block(mods[m].source, command.replace("-", "_"))
        if block and SERVER_CALL.search(block):
            return True
    return False

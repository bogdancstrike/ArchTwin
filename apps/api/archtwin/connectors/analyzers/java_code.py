"""Java (and the Java-syntax subset of Spring code) understood structurally with tree-sitter.

What a Spring / Jakarta codebase declares, statically and deterministically:
* structure: packages, classes/interfaces/records, stereotypes (@RestController, @Service, @Repository, @Component,
  @Configuration, @Entity), injected collaborators (constructor/field injection), inheritance;
* modules: Spring Modulith `@ApplicationModule` packages (display name, allowed dependencies, `@NamedInterface`s) or, without
  Modulith, the packages directly below the application package; dependencies between modules, access to another module's
  internal types (boundary violations) and dependency cycles;
* entry points: Spring MVC / WebFlux routes (class + method mappings), JAX-RS, websocket handlers, `@Scheduled` jobs, message
  listeners (application events, Kafka, Rabbit, JMS, Redis pub/sub and streams);
* effects per method, followed through injected collaborators: SQL tables read/written (JDBC strings, text blocks), events
  published, Redis channels/streams, Kafka topics, outgoing HTTP calls, object storage;
* JPA entities (`@Entity` / `@Table`).
Names built at run time are kept as patterns (`"mail:" + id` -> `mail:*`) or left out — never guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

V_JAVA = "java-treesitter/1.0"

STEREOTYPES = {"RestController": "controller", "Controller": "controller", "Service": "service", "Repository": "repository",
               "Component": "component", "Configuration": "configuration", "Entity": "entity", "SpringBootApplication": "application",
               "ControllerAdvice": "controller-advice", "RestControllerAdvice": "controller-advice", "FeignClient": "http-client",
               "WorkflowInterface": "workflow", "ActivityInterface": "activity", "Path": "controller"}
MAPPINGS = {"GetMapping": "GET", "PostMapping": "POST", "PutMapping": "PUT", "DeleteMapping": "DELETE", "PatchMapping": "PATCH"}
JAXRS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
EVENT_LISTENERS = {"EventListener", "ApplicationModuleListener", "TransactionalEventListener", "DomainEventHandler"}
MQ_LISTENERS = {"KafkaListener": ("kafka", "topics"), "RabbitListener": ("rabbitmq", "queues"), "JmsListener": ("jms", "destination"),
                "SqsListener": ("sqs", "value"), "StreamListener": ("stream", "value")}
SQL_READ = re.compile(r"\b(?:from|join)\s+(?:only\s+)?([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)", re.IGNORECASE)
SQL_WRITE = re.compile(r"\b(?:insert\s+into|update|delete\s+from|merge\s+into|truncate(?:\s+table)?)\s+(?:only\s+)?([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)",
                       re.IGNORECASE)
SQL_HINT = re.compile(r"^\s*(?:select|insert|update|delete|with|merge|truncate)\b|\b(?:from|into|update)\s+[a-z_]", re.IGNORECASE)
SQL_NOT_TABLES = {"select", "where", "set", "values", "lateral", "unnest", "jsonb_array_elements", "generate_series", "dual",
                  "the", "a", "an", "to", "this", "that", "now", "current_timestamp", "information_schema", "pg_catalog"}
PUBLISH_EVENT = re.compile(r"\b(?:publishEvent|publish|registerEvent|raise|emit)\s*\(\s*new\s+(?:[a-z_]\w*\.)*([A-Z]\w*)\s*[(<]")
PUBLISH_FACTORY = re.compile(r"\bpublishEvent\s*\(\s*(?:[a-z_]\w*\.)*([A-Z]\w*)\.(?:of|from|create|new\w*)\s*\(")
REDIS_PUB = re.compile(r"\b(?:convertAndSend|publish)\s*\(\s*(?P<arg>[^,)]{1,160})")
REDIS_SUB = re.compile(r"\b(?:ChannelTopic|PatternTopic)(?:\.of)?\s*\(\s*(?P<arg>[^)]{1,160})\)|new\s+(?:ChannelTopic|PatternTopic)\s*\(\s*(?P<arg2>[^)]{1,160})\)")
REDIS_STREAM_ADD = re.compile(r"(?:opsForStream\(\)\s*\.\s*add|xAdd|xadd|withStreamKey)\s*\(\s*(?P<arg>[^,)]{1,160})")
REDIS_STREAM_READ = re.compile(r"StreamOffset\s*\.\s*(?:create|fromStart|latest|lastConsumed)\s*\(\s*(?P<arg>[^,)]{1,160})|"
                               r"(?:xReadGroup|xread|xreadgroup|createGroup)\s*\(\s*(?P<arg2>[^,)]{1,160})")
KAFKA_SEND = re.compile(r"\b(?:kafkaTemplate|template|producer)\s*\.\s*send\s*\(\s*(?P<arg>[^,)]{1,160})", re.IGNORECASE)
HTTP_BASE = re.compile(r"""(?:baseUrl|create|uri|getForObject|getForEntity|postForObject|postForEntity|exchange)\s*\(\s*"(?P<url>https?://[^"]+)\"""")
S3_USE = re.compile(r"\b(?:S3Client|S3AsyncClient|AmazonS3|MinioClient|S3Presigner)\b")
STRING_LIT = re.compile(r'"""(.*?)"""|"((?:[^"\\\n]|\\.)*)"', re.DOTALL)


@lru_cache(maxsize=1)
def _parser():
    import tree_sitter_java
    from tree_sitter import Language, Parser
    return Parser(Language(tree_sitter_java.language()))


@dataclass
class Method:
    name: str
    line: int
    end: int
    body: str
    annotations: dict[str, str] = field(default_factory=dict)    # annotation name -> argument text
    params: list[tuple[str, str]] = field(default_factory=list)  # (type, name)


@dataclass
class JClass:
    fqcn: str
    name: str
    kind: str                                                    # class | interface | record | enum
    package: str
    path: Path
    line: int
    annotations: dict[str, str] = field(default_factory=dict)
    extends: list[str] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)         # field / constructor-param name -> simple type
    methods: list[Method] = field(default_factory=list)
    consts: dict[str, str] = field(default_factory=dict)         # static final String X = "..."
    imports: dict[str, str] = field(default_factory=dict)        # simple name -> fqcn (file imports)

    @property
    def stereotype(self) -> str:
        for a in self.annotations:
            if a in STEREOTYPES:
                return STEREOTYPES[a]
        return ""


@dataclass
class Route:
    method: str
    path: str
    cls: str
    handler: str
    line: int
    kind: str = "http"                                          # http | ws | scheduled | listener


def _text(n) -> str:
    return n.text.decode("utf-8", "replace") if n is not None else ""


def _strings(arg: str) -> list[str]:
    return [m.group(1) if m.group(1) is not None else m.group(2) for m in STRING_LIT.finditer(arg)]


def annotation_value(args: str, *keys: str) -> list[str]:
    """String values of an annotation: positional ("x" or {"a","b"}) or named (path = "x", value = {...})."""
    if not args:
        return []
    for k in keys:
        m = re.search(rf"\b{k}\s*=\s*(\{{[^}}]*\}}|\"(?:[^\"\\]|\\.)*\"|[\w.]+)", args)
        if m:
            return _strings(m.group(1)) or [m.group(1)]
    if "=" not in args.split('"', 1)[0]:                         # positional first argument
        return _strings(args.split(",", 1)[0] if not args.lstrip().startswith("{") else args[: args.find("}") + 1])
    return []


def _annotations(mods_node) -> dict[str, str]:
    out: dict[str, str] = {}
    if mods_node is None:
        return out
    for c in mods_node.children:
        if c.type in ("marker_annotation", "annotation"):
            name = _text(c.child_by_field_name("name")).split(".")[-1]
            args = c.child_by_field_name("arguments")
            out[name] = _text(args)[1:-1] if args is not None else ""
    return out


def _simple(t: str) -> str:
    """`List<Foo>` -> `Foo`, `Optional<com.x.Bar>` -> `Bar`, `Foo[]` -> `Foo`."""
    inner = re.findall(r"<\s*([\w.]+)", t)
    base = inner[-1] if inner and t.split("<")[0].split(".")[-1] in ("List", "Set", "Optional", "Collection", "Iterable", "Provider",
                                                                      "ObjectProvider", "Supplier", "Map", "Flux", "Mono") else t.split("<")[0]
    return base.replace("[]", "").split(".")[-1].strip()


def parse_file(path: Path, source: bytes) -> tuple[str, list[JClass]]:
    tree = _parser().parse(source)
    root = tree.root_node
    package, imports = "", {}
    for c in root.children:
        if c.type == "package_declaration":
            package = next((_text(x) for x in c.children if x.type in ("scoped_identifier", "identifier")), "")
        elif c.type == "import_declaration":
            t = _text(c).removeprefix("import").removesuffix(";").strip()
            if not t.startswith("static ") and not t.endswith(".*"):
                imports[t.split(".")[-1]] = t
    classes: list[JClass] = []

    def walk_class(n, outer: str) -> None:
        name = _text(n.child_by_field_name("name"))
        kind = {"class_declaration": "class", "interface_declaration": "interface", "record_declaration": "record",
                "enum_declaration": "enum", "annotation_type_declaration": "annotation"}[n.type]
        fq = f"{package}.{outer}{name}" if package else f"{outer}{name}"
        mods = next((c for c in n.children if c.type == "modifiers"), None)
        jc = JClass(fq, name, kind, package, path, n.start_point[0] + 1, _annotations(mods), imports=imports)
        for fld in ("superclass", "interfaces"):
            sub = n.child_by_field_name(fld)
            if sub is not None:
                jc.extends += [_simple(x) for x in re.findall(r"[\w.]+(?:<[^>]*>)?", _text(sub).replace("extends", " ").replace("implements", " "))
                               if x not in ("extends", "implements")]
        ext = next((c for c in n.children if c.type == "extends_interfaces"), None)
        if ext is not None:
            jc.extends += [_simple(x) for x in re.findall(r"[\w.]+", _text(ext).replace("extends", " "))]
        if kind == "record":
            ps = n.child_by_field_name("parameters")
            for p in (ps.children if ps is not None else []):
                if p.type == "formal_parameter":
                    jc.fields[_text(p.child_by_field_name("name"))] = _simple(_text(p.child_by_field_name("type")))
        body = n.child_by_field_name("body")
        for m in (body.children if body is not None else []):
            if m.type == "field_declaration":
                ftype = _simple(_text(m.child_by_field_name("type")))
                fmods = _text(next((c for c in m.children if c.type == "modifiers"), None))
                for d in m.children:
                    if d.type == "variable_declarator":
                        vname = _text(d.child_by_field_name("name"))
                        val = d.child_by_field_name("value")
                        if "static" in fmods and "final" in fmods and val is not None and val.type == "string_literal":
                            jc.consts[vname] = (_strings(_text(val)) or [""])[0]
                        elif "static" not in fmods:
                            jc.fields[vname] = ftype
            elif m.type in ("method_declaration", "constructor_declaration"):
                mname = _text(m.child_by_field_name("name"))
                params = []
                ps = m.child_by_field_name("parameters")
                for p in (ps.children if ps is not None else []):
                    if p.type in ("formal_parameter", "spread_parameter"):
                        params.append((_simple(_text(p.child_by_field_name("type"))), _text(p.child_by_field_name("name"))))
                b = m.child_by_field_name("body")
                meth = Method(mname, m.start_point[0] + 1, m.end_point[0] + 1, _text(b),
                              _annotations(next((c for c in m.children if c.type == "modifiers"), None)), params)
                if m.type == "constructor_declaration":
                    for t, pn in params:                          # constructor injection
                        jc.fields.setdefault(pn, t)
                else:
                    jc.methods.append(meth)
            elif m.type in ("class_declaration", "interface_declaration", "record_declaration", "enum_declaration"):
                walk_class(m, f"{outer}{name}.")
        classes.append(jc)

    for c in root.children:
        if c.type in ("class_declaration", "interface_declaration", "record_declaration", "enum_declaration", "annotation_type_declaration"):
            walk_class(c, "")
    return package, classes


# ---------------------------------------------------------------- codebase model
@dataclass
class Module:
    name: str                       # package segment below the application package
    package: str
    display: str
    explicit: bool                  # declared with @ApplicationModule
    allowed: list[str] = field(default_factory=list)
    named_interfaces: dict[str, str] = field(default_factory=dict)   # package -> interface name
    path: str = ""


@dataclass
class JavaCodebase:
    classes: dict[str, JClass]
    base_package: str
    modules: dict[str, Module]
    module_of: dict[str, str]        # fqcn -> module name
    by_simple: dict[str, list[str]]
    implementers: dict[str, list[str]]
    package_info: dict[str, dict[str, str]]

    def resolve(self, simple: str, ctx: JClass) -> JClass | None:
        """A simple type name in the context of a class: its imports, its package, then the only class with that name."""
        fq = ctx.imports.get(simple)
        if fq and fq in self.classes:
            return self.classes[fq]
        same = f"{ctx.package}.{simple}"
        if same in self.classes:
            return self.classes[same]
        cands = self.by_simple.get(simple, [])
        return self.classes[cands[0]] if len(cands) == 1 else None

    def concrete(self, jc: JClass) -> list[JClass]:
        """An interface -> its implementations in the codebase (Spring injects those); a class -> itself."""
        if jc.kind != "interface":
            return [jc]
        return [self.classes[f] for f in self.implementers.get(jc.name, []) if f in self.classes] or [jc]


def _is_test(rel_parts: tuple[str, ...]) -> bool:
    return "test" in rel_parts or "tests" in rel_parts or "testFixtures" in rel_parts


def analyze(context_dir: Path, files: list[Path], read_bytes, errors: list[str] | None = None) -> JavaCodebase | None:
    classes: dict[str, JClass] = {}
    package_info: dict[str, dict[str, str]] = {}
    for f in files:
        if f.suffix != ".java" or _is_test(f.relative_to(context_dir).parts) or f.stat().st_size > 800_000:
            continue
        try:
            src = read_bytes(f)
            if f.name == "package-info.java":
                pkg = re.search(rb"^\s*package\s+([\w.]+)\s*;", src, re.MULTILINE)
                if pkg:
                    package_info[pkg.group(1).decode()] = _annotations_from_text(src.decode("utf-8", "replace"))
                continue
            _, cls = parse_file(f, src)
            for c in cls:
                classes[c.fqcn] = c
        except Exception as e:  # noqa: BLE001 — never abort a scan on one file; reported by the caller
            if errors is not None:
                errors.append(f"{f.name}: {type(e).__name__}: {str(e)[:120]}")
    if not classes:
        return None
    apps = [c for c in classes.values() if "SpringBootApplication" in c.annotations or "QuarkusMain" in c.annotations]
    if apps:
        base = min((c.package for c in apps), key=len)
    else:
        pkgs = sorted({c.package for c in classes.values() if c.package})
        base = _common_prefix(pkgs)
    modules: dict[str, Module] = {}
    module_of: dict[str, str] = {}
    for fq, c in classes.items():
        rest = c.package[len(base):].lstrip(".") if c.package.startswith(base) else ""
        seg = rest.split(".")[0] if rest else ""
        if not seg:
            continue
        mpkg = f"{base}.{seg}" if base else seg
        if seg not in modules:
            info = package_info.get(mpkg, {})
            am = info.get("ApplicationModule")
            display = (annotation_value(am or "", "displayName") or [seg])[0] if am is not None else seg
            allowed = annotation_value(am or "", "allowedDependencies") if am is not None else []
            modules[seg] = Module(seg, mpkg, display, am is not None, allowed)
        module_of[fq] = seg
    for pkg, info in package_info.items():
        if "NamedInterface" in info:
            rest = pkg[len(base):].lstrip(".") if pkg.startswith(base) else ""
            seg = rest.split(".")[0] if rest else ""
            if seg in modules:
                modules[seg].named_interfaces[pkg] = (annotation_value(info["NamedInterface"], "value", "name") or [pkg.split(".")[-1]])[0]
    by_simple: dict[str, list[str]] = {}
    implementers: dict[str, list[str]] = {}
    for fq, c in classes.items():
        by_simple.setdefault(c.name, []).append(fq)
        for e in c.extends:
            implementers.setdefault(e, []).append(fq)
    return JavaCodebase(classes, base, modules, module_of, by_simple, implementers, package_info)


def _annotations_from_text(src: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(r"@([\w.]+)\s*(\((?:[^()]|\([^()]*\))*\))?", src):
        out[m.group(1).split(".")[-1]] = (m.group(2) or "()")[1:-1]
    return out


def _common_prefix(pkgs: list[str]) -> str:
    if not pkgs:
        return ""
    parts = [p.split(".") for p in pkgs]
    out = []
    for segs in zip(*parts, strict=False):
        if len(set(segs)) != 1:
            break
        out.append(segs[0])
    # keep at least the organisation prefix; modules are the next level
    return ".".join(out[: max(1, len(out))]) if len(set(pkgs)) > 1 else ".".join(out[:-1]) or ".".join(out)


# ---------------------------------------------------------------- module dependencies and boundaries
def module_dependencies(cb: JavaCodebase) -> dict[tuple[str, str], dict[str, Any]]:
    """(from module, to module) -> {count, internal: [types of the target's internals used], allowed: bool}."""
    deps: dict[tuple[str, str], dict[str, Any]] = {}
    for fq, c in cb.classes.items():
        a = cb.module_of.get(fq)
        if not a:
            continue
        used = set(c.imports.values()) | {t for t in c.fields.values()}
        for u in used:
            target = cb.classes.get(u) or cb.resolve(u, c) if "." not in u else cb.classes.get(u)
            if target is None:
                continue
            b = cb.module_of.get(target.fqcn)
            if not b or b == a:
                continue
            d = deps.setdefault((a, b), {"count": 0, "internal": set(), "types": set()})
            d["count"] += 1
            d["types"].add(target.name)
            mod = cb.modules[b]
            public = target.package == mod.package or target.package in mod.named_interfaces or \
                any(target.package.startswith(p + ".") for p in mod.named_interfaces)
            if not public and mod.explicit:
                d["internal"].add(target.fqcn)
    for (a, b), d in deps.items():
        allowed = cb.modules[a].allowed
        d["allowed"] = (not allowed) or any(x.split("::")[0] == b for x in allowed)
        d["internal"] = sorted(d["internal"])[:20]
        d["types"] = sorted(d["types"])[:20]
    return deps


def cycles(edges: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Edges that lie on a dependency cycle (Tarjan SCCs of size > 1)."""
    graph: dict[str, list[str]] = {}
    for a, b in edges:
        graph.setdefault(a, []).append(b)
        graph.setdefault(b, [])
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on: set[str] = set()
    comp: dict[str, int] = {}
    counter = [0, 0]

    def strong(v: str) -> None:
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in graph[v]:
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            while True:
                w = stack.pop()
                on.discard(w)
                comp[w] = counter[1]
                if w == v:
                    break
            counter[1] += 1
    import sys
    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    for v in graph:
        if v not in index:
            strong(v)
    sizes: dict[int, int] = {}
    for c in comp.values():
        sizes[c] = sizes.get(c, 0) + 1
    return {(a, b) for a, b in edges if comp[a] == comp[b] and sizes[comp[a]] > 1}


# ---------------------------------------------------------------- entry points
def _join(prefix: str, path: str) -> str:
    p = "/" + "/".join(x.strip("/") for x in (prefix, path) if x and x.strip("/"))
    return p if p != "" else "/"


def routes(cb: JavaCodebase) -> list[Route]:
    out: list[Route] = []
    for fq, c in cb.classes.items():
        prefixes = annotation_value(c.annotations.get("RequestMapping", ""), "path", "value") or \
            annotation_value(c.annotations.get("Path", ""), "value") or [""]
        is_web = c.stereotype == "controller" or "RequestMapping" in c.annotations or "Path" in c.annotations
        for m in c.methods:
            for ann, verb in MAPPINGS.items():
                if ann in m.annotations and is_web:
                    for p in annotation_value(m.annotations[ann], "path", "value") or [""]:
                        for pre in prefixes:
                            out.append(Route(verb, _join(pre, p), fq, m.name, m.line))
            if "RequestMapping" in m.annotations and is_web:
                args = m.annotations["RequestMapping"]
                verbs = re.findall(r"RequestMethod\.(\w+)", args) or ["GET"]
                for p in annotation_value(args, "path", "value") or [""]:
                    for pre in prefixes:
                        out += [Route(v, _join(pre, p), fq, m.name, m.line) for v in verbs]
            jax = [a for a in m.annotations if a in JAXRS]
            if jax and ("Path" in c.annotations or "Path" in m.annotations):
                sub = (annotation_value(m.annotations.get("Path", ""), "value") or [""])[0]
                out += [Route(v, _join(pre, sub), fq, m.name, m.line) for v in jax for pre in prefixes]
            if "Scheduled" in m.annotations:
                a = m.annotations["Scheduled"]
                when = (re.search(r"(cron|fixedDelay\w*|fixedRate\w*|initialDelay\w*)\s*=\s*(\"[^\"]*\"|[\w.]+)", a) or None)
                out.append(Route("SCHEDULED", f"{c.name}.{m.name}" + (f" ({when.group(1)} {when.group(2).strip(chr(34))})" if when else ""),
                                 fq, m.name, m.line, "scheduled"))
            for ann in ("MessageMapping", "SubscribeMapping"):
                if ann in m.annotations:
                    for p in annotation_value(m.annotations[ann], "value") or [""]:
                        out.append(Route("STOMP", _join("", p), fq, m.name, m.line, "ws"))
        # websocket handlers registered in configuration: registry.addHandler(handler, "/ws")
        for m in c.methods:
            for wm in re.finditer(r"addHandler\s*\(", m.body):
                args = _call_args(m.body, wm.end())
                if len(args) < 2:
                    continue
                target = re.sub(r"\(\)$", "", args[0]).split(".")[-1]
                tcls = c.fields.get(target) or (target[:1].upper() + target[1:])
                for a in args[1:]:
                    for p in eval_string(a, c, cb, m):
                        out.append(Route("WS", p, (cb.resolve(tcls, c) or c).fqcn, "handleTextMessage", m.line, "ws"))
            for wm in re.finditer(r"addEndpoint\s*\(\s*((?:\"[^\"]*\"\s*,?\s*)+)", m.body):
                out += [Route("WS", p, fq, m.name, m.line, "ws") for p in _strings(wm.group(1))]
        if "ServerEndpoint" in c.annotations:
            out += [Route("WS", p, fq, "onMessage", c.line, "ws") for p in annotation_value(c.annotations["ServerEndpoint"], "value")]
    return out


@dataclass
class Listener:
    technology: str                 # spring-event | kafka | rabbitmq | jms | redis-pubsub | redis-stream
    channel: str                    # event type / topic / queue / channel pattern
    cls: str
    method: str
    line: int


def _split_plus(expr: str) -> list[str]:
    parts, depth, cur, q = [], 0, [], ""
    for ch in expr:
        if q:
            cur.append(ch)
            if ch == q:
                q = ""
            continue
        if ch == '"':
            q = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "+" and depth == 0:
            parts.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur))
    return [x.strip() for x in parts if x.strip()]


def eval_string(expr: str, c: JClass, cb: JavaCodebase | None = None, m: Method | None = None, depth: int = 2,
                bind: dict[str, list[str]] | None = None) -> list[str]:
    """Static value(s) of a String expression as patterns: literals, constants (own or `Other.CONST`), concatenation,
    `"fmt".formatted(..)` / `String.format`, a local variable, or a parameter resolved through its call sites in the class.
    Unknown parts become `*`; a result without two literal letters is unknowable and dropped."""
    expr = expr.strip()
    results = [""]
    for tok in _split_plus(expr):
        vals: list[str]
        lit = re.fullmatch(r'"((?:[^"\\]|\\.)*)"(?:\s*\.\s*formatted\s*\(.*\))?', tok, re.DOTALL)
        fmt = re.fullmatch(r'String\s*\.\s*format\s*\(\s*"((?:[^"\\]|\\.)*)".*', tok, re.DOTALL)
        const = re.fullmatch(r"(?:([A-Z]\w*)\.)?([A-Z][A-Z0-9_]+)", tok)
        ident = re.fullmatch(r"[a-z]\w*", tok)
        if lit or fmt:
            vals = [re.sub(r"%[sdx]|\{\}", "*", (lit or fmt).group(1))]
        elif const:
            owner = (cb.resolve(const.group(1), c) if (const.group(1) and cb) else c) or c
            v = owner.consts.get(const.group(2))
            vals = [v] if v is not None else ["*"]
        elif ident and bind and tok in bind:
            vals = bind[tok] or ["*"]
        elif ident and m is not None and depth > 0:
            local = re.search(rf"(?:String|var)\s+{tok}\s*=\s*([^;]+);", m.body)
            if local:
                vals = eval_string(local.group(1), c, cb, m, depth - 1) or ["*"]
            elif any(pn == tok for _, pn in m.params):
                idx = [pn for _, pn in m.params].index(tok)
                vals = []
                for other in c.methods:
                    for call in re.finditer(rf"(?<![\w.]){re.escape(m.name)}\s*\(", other.body):
                        args = _call_args(other.body, call.end())
                        if idx < len(args):
                            vals += eval_string(args[idx], c, cb, other, depth - 1)
                vals = vals or ["*"]
            else:
                vals = ["*"]
        else:
            vals = ["*"]
        results = [r + v for r in results for v in vals][:8]
    out = []
    for r in results:
        r = re.sub(r"\*+", "*", r)
        if re.search(r"[A-Za-z]{2}", r) and r not in out:
            out.append(r)
    return out


def _call_args(text: str, start: int, limit: int = 400) -> list[str]:
    depth, cur, args, q = 0, [], [], ""
    for ch in text[start: start + limit]:
        if q:
            cur.append(ch)
            if ch == q:
                q = ""
            continue
        if ch == '"':
            q = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                args.append("".join(cur))
                return [a.strip() for a in args if a.strip()]
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    return []


def _arg_pattern(arg: str, c: JClass, cb: JavaCodebase | None = None, m: Method | None = None) -> str | None:
    vals = eval_string(arg, c, cb, m)
    return vals[0] if vals else None


def _arg_patterns(arg: str, c: JClass, cb: JavaCodebase | None, m: Method | None,
                  bind: dict[str, list[str]] | None = None) -> list[str]:
    return eval_string(arg, c, cb, m, bind=bind)


def listeners(cb: JavaCodebase) -> list[Listener]:
    out: list[Listener] = []
    for fq, c in cb.classes.items():
        for m in c.methods:
            for ann in EVENT_LISTENERS & set(m.annotations):
                classes = re.findall(r"([A-Z]\w*)\.class", m.annotations[ann])
                types = classes or [t for t, _ in m.params[:1]]
                out += [Listener("spring-event", t, fq, m.name, m.line) for t in types if t and t[0].isupper()]
            for ann, (tech, key) in MQ_LISTENERS.items():
                if ann in m.annotations:
                    for t in annotation_value(m.annotations[ann], key, "value", "topics", "queues"):
                        out.append(Listener(tech, t, fq, m.name, m.line))
            for rx, tech in ((REDIS_SUB, "redis-pubsub"), (REDIS_STREAM_READ, "redis-stream")):
                for mm in rx.finditer(m.body):
                    for pat in _arg_patterns(mm.group("arg") or mm.group("arg2") or "", c, cb, m):
                        out.append(Listener(tech, pat, fq, m.name, m.line))
        if any(e in ("ApplicationListener",) for e in c.extends):
            gen = re.search(r"ApplicationListener<\s*(\w+)", "")
            if gen:
                out.append(Listener("spring-event", gen.group(1), fq, "onApplicationEvent", c.line))
    return out


# ---------------------------------------------------------------- effects of code, followed through injected collaborators
@dataclass
class Effects:
    reads: set[str] = field(default_factory=set)       # tables
    writes: set[str] = field(default_factory=set)
    events: set[str] = field(default_factory=set)      # application events published
    pubsub: set[str] = field(default_factory=set)      # redis channels published
    streams: set[str] = field(default_factory=set)     # redis streams appended
    topics: set[str] = field(default_factory=set)      # kafka topics
    urls: set[str] = field(default_factory=set)        # outgoing http base URLs
    storage: bool = False
    modules: set[str] = field(default_factory=set)     # other modules' code invoked
    calls: list[tuple[str, str]] = field(default_factory=list)   # (class fqcn, method) visited

    def merge(self, o: Effects) -> None:
        for k in ("reads", "writes", "events", "pubsub", "streams", "topics", "urls", "modules"):
            getattr(self, k).update(getattr(o, k))
        self.storage = self.storage or o.storage


def sql_tables(text: str) -> tuple[set[str], set[str]]:
    reads, writes = set(), set()
    for m in STRING_LIT.finditer(text):
        s = m.group(1) if m.group(1) is not None else (m.group(2) or "")
        if not SQL_HINT.search(s):
            continue
        for w in SQL_WRITE.findall(s):
            t = w.split(".")[-1].lower()
            if t not in SQL_NOT_TABLES:
                writes.add(t)
        for r in SQL_READ.findall(s):
            t = r.split(".")[-1].lower()
            if t not in SQL_NOT_TABLES and t not in writes:
                reads.add(t)
    return reads, writes


def method_effects(cb: JavaCodebase, c: JClass, m: Method, depth: int = 3, seen: set[tuple[str, str]] | None = None,
                   bind: dict[str, list[str]] | None = None) -> Effects:
    seen = seen if seen is not None else set()
    fx = Effects()
    sig = (c.fqcn, m.name, tuple(sorted((k, tuple(v)) for k, v in (bind or {}).items())))
    if sig in seen:
        return fx
    seen.add(sig)
    fx.calls.append((c.fqcn, m.name))
    body = m.body
    r, w = sql_tables(body + "\n" + "\n".join(f'"{v}"' for k, v in c.consts.items() if re.search(rf"\b{k}\b", body)))
    fx.reads |= r
    fx.writes |= w
    fx.events |= set(PUBLISH_EVENT.findall(body)) | set(PUBLISH_FACTORY.findall(body))
    for mm in REDIS_PUB.finditer(body):
        if "convertAndSend" in mm.group(0) or "redis" in body.lower() or "valkey" in body.lower():
            fx.pubsub |= {p for p in _arg_patterns(mm.group("arg"), c, cb, m, bind) if not p[0].isupper()}
    for mm in REDIS_STREAM_ADD.finditer(body):
        fx.streams |= set(_arg_patterns(mm.group("arg"), c, cb, m, bind))
    for mm in KAFKA_SEND.finditer(body):
        fx.topics |= set(_arg_patterns(mm.group("arg"), c, cb, m, bind))
    fx.urls |= {u.group("url") for u in HTTP_BASE.finditer(body)}
    fx.storage = bool(S3_USE.search(body)) or any(S3_USE.search(t) and re.search(rf"\b{re.escape(n)}\b", body)
                                                  for n, t in c.fields.items())
    if depth <= 0:
        return fx
    # this.helper(...) and collaborator.method(...) through injected fields (interfaces -> implementations)
    for call in re.finditer(r"(?<![\w.])(?:this\.)?([a-z]\w*)\s*\(", body):
        own = next((x for x in c.methods if x.name == call.group(1)), None)
        if own is None or own is m:
            continue
        args = _call_args(body, call.end())        # bind the helper's parameters to THIS call's arguments
        sub_bind = {pn: eval_string(a, c, cb, m, bind=bind) for (_, pn), a in zip(own.params, args, strict=False)}
        fx.merge(method_effects(cb, c, own, depth - 1, seen, sub_bind))
    refs = set(re.findall(r"(?<![\w.])(?:this\.)?([a-z]\w*)\s*\.\s*([a-zA-Z]\w*)\s*\(", body))
    refs |= set(re.findall(r"(?<![\w.])(?:this\.)?([a-z]\w*)\s*::\s*([a-zA-Z]\w*)", body))      # hints::signalMail
    for fname, meth in refs:
        t = c.fields.get(fname)
        if not t:
            continue
        target = cb.resolve(t, c)
        if target is None:
            continue
        for impl in cb.concrete(target):
            mod = cb.module_of.get(impl.fqcn)
            if mod and mod != cb.module_of.get(c.fqcn):
                fx.modules.add(mod)
            for x in impl.methods:
                if x.name == meth:
                    sub = method_effects(cb, impl, x, depth - 1, seen)
                    fx.merge(sub)
                    fx.calls += sub.calls
    return fx


def entities(cb: JavaCodebase) -> list[tuple[str, JClass]]:
    """JPA / Spring Data JDBC entities -> (table name, class)."""
    out = []
    for c in cb.classes.values():
        if "Entity" in c.annotations or ("Table" in c.annotations and c.kind in ("class", "record")):
            t = annotation_value(c.annotations.get("Table", ""), "name", "value")
            out.append(((t[0] if t else re.sub(r"(?<!^)(?=[A-Z])", "_", c.name)).lower(), c))
    return out

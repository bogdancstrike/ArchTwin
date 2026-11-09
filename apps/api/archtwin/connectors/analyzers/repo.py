"""Static discovery over a checked-out repository tree (origin = static).

Produces a deterministic ScanResult from files only (no network): compose services and their wiring, Dockerfiles,
mounted configuration, Python import graphs and routes (tree-sitter), TS/web components, OpenAPI contracts, Backstage
catalog, CODEOWNERS, package manifests and Markdown documents. Each analyzer has its own parser_version.
"""
from __future__ import annotations

import fnmatch
import json
import re
import shlex
import tomllib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from archtwin.connectors.analyzers import db_schema, gateway_maps, python_code, resources, webui
from archtwin.connectors.analyzers.common import HOSTPORT_RX, SCHEME_REL, URL_RX, classify, read, safe_url, scheme_base, walk
from archtwin.connectors.sdk import DocumentOut, ScanResult

V_COMPOSE = "compose/1.1"
V_DOCKERFILE = "dockerfile/1.0"
V_CONFIG = "config-urls/1.0"
V_MANIFEST = "pkg-manifest/1.0"
V_OPENAPI = "openapi/1.0"
V_CATALOG = "backstage/1.0"
V_CODEOWNERS = "codeowners/1.0"
V_TS = "ts-imports/1.0"
V_DOCS = "markdown/1.0"
V_INFER = "infer/1.0"
V_XREPO = "config-urls-xrepo/1.0"
V_DIAGRAM = "doc-diagrams/1.0"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal", "example.com", "example.org"}
IP_RX = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def name_ref(host: str) -> str | None:
    """A host that may be a service in ANOTHER repository/datasource -> `name:<service>` (resolved by the graph builder
    across all datasources; unresolved names are dropped, never invented). Public FQDNs and local hosts are skipped."""
    h = host.lower().strip(".")
    if not h or h in LOCAL_HOSTS or IP_RX.match(h) or "${" in h:
        return None
    for suffix in (".svc.cluster.local", ".svc", ".cluster.local"):
        if h.endswith(suffix):
            return "name:" + h[: -len(suffix)].split(".")[0]
    return None if "." in h else f"name:{h}"


DIAGRAM_REL = [(re.compile(r"publish|produc|emit|send event", re.IGNORECASE), "publishes"), (re.compile(r"consum|subscrib|listen", re.IGNORECASE), "consumes"),
               (re.compile(r"\bwrite|store|persist|insert|save", re.IGNORECASE), "writes"), (re.compile(r"\bread|query|fetch|load", re.IGNORECASE), "reads")]
MERMAID_NODE = re.compile(r"(?<![\w\-])([A-Za-z0-9_][A-Za-z0-9_\-]*)\s*(?:\[\(|\(\(|\[\[|\[/|\[|\(|\{\{|\{)\s*\"?([^\]\)\}\"|]{1,80})\"?\s*(?:\)\]|\)\)|\]\]|/\]|\]|\)|\}\}|\})")
MERMAID_EDGE = re.compile(r"([A-Za-z0-9_\-]+)(?:\s*(?:\[[^\]]*\]|\([^)]*\)|\{[^}]*\}))?\s*(?:-->|-\.->|==>|---|-->>|->>|--\)|-\)|->)\s*(?:\|([^|]{0,80})\|)?\s*([A-Za-z0-9_\-]+)(?:\s*:\s*(.{0,80}))?")
MERMAID_LABELED = re.compile(r"([A-Za-z0-9_\-]+)(?:\s*(?:\[[^\]]*\]|\([^)]*\)))?\s*--\s*([^->][^-]{0,60}?)\s*-->\s*([A-Za-z0-9_\-]+)")
PUML_EDGE = re.compile(r"^\s*\[?\"?([A-Za-z0-9_\- ]+?)\"?\]?\s*-+(?:>|\.>)\s*\[?\"?([A-Za-z0-9_\- ]+?)\"?\]?\s*(?::\s*(.{0,80}))?$")
PUML_ALIAS = re.compile(r"^\s*(?:component|node|database|queue|actor|participant|rectangle|interface|cloud|frame|package)\s+\"?([^\"]+?)\"?\s+as\s+([A-Za-z0-9_]+)", re.IGNORECASE)
DSL_ALIAS = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=\s*(?:softwareSystem|container|component|person)\s+\"([^\"]+)\"", re.IGNORECASE)
DSL_EDGE = re.compile(r"^\s*([A-Za-z0-9_.]+)\s*->\s*([A-Za-z0-9_.]+)\s*(?:\"([^\"]*)\")?")
SKIP_DIAGRAM_NAMES = {"user", "users", "client", "browser", "start", "end", "a", "b", "c", "x", "y"}


def diagram_edges(lang: str, src: str) -> list[tuple[str, str, str, str]]:
    """(source name, relation, target name, label) from Mermaid flowchart/sequence, PlantUML or Structurizr DSL text.
    Pure text parsing — the names are matched to real elements by the graph builder."""
    labels: dict[str, str] = {}
    out: list[tuple[str, str, str, str]] = []
    lines = src.splitlines()
    if lang == "mermaid":
        for ln in lines:
            for m in MERMAID_NODE.finditer(ln):
                labels.setdefault(m.group(1), m.group(2).strip())
            pm = re.match(r"^\s*participant\s+([A-Za-z0-9_\-]+)(?:\s+as\s+(.+))?", ln)
            if pm:
                labels[pm.group(1)] = (pm.group(2) or pm.group(1)).strip()
        for ln in lines:
            hits = [(m.group(1), m.group(3), m.group(2).strip()) for m in MERMAID_LABELED.finditer(ln)]
            rest = MERMAID_LABELED.sub(" ", ln)                 # "a -- text --> b" must not also yield "text --> b"
            hits += [(m.group(1), m.group(3), (m.group(2) or m.group(4) or "").strip()) for m in MERMAID_EDGE.finditer(rest)]
            for a, b, label in hits:
                out.append((labels.get(a, a), "", labels.get(b, b), label))
    elif lang == "plantuml":
        for ln in lines:
            am = PUML_ALIAS.match(ln)
            if am:
                labels[am.group(2)] = am.group(1).strip()
        for ln in lines:
            m = PUML_EDGE.match(ln)
            if m:
                out.append((labels.get(m.group(1).strip(), m.group(1).strip()), "", labels.get(m.group(2).strip(), m.group(2).strip()), m.group(3) or ""))
    elif lang == "structurizr":
        for ln in lines:
            am = DSL_ALIAS.match(ln)
            if am:
                labels[am.group(1)] = am.group(2)
        for ln in lines:
            m = DSL_EDGE.match(ln)
            if m:
                a, b = m.group(1).split(".")[-1], m.group(2).split(".")[-1]
                out.append((labels.get(a, a), "", labels.get(b, b), m.group(3) or ""))
    res = []
    for a, _, b, label in out:
        if a == b or a.lower() in SKIP_DIAGRAM_NAMES or b.lower() in SKIP_DIAGRAM_NAMES:
            continue
        rel = next((r for rx, r in DIAGRAM_REL if rx.search(label)), "calls")
        res.append((a, rel, b, label))
    return list(dict.fromkeys(res))

KNOWN_EXTERNAL_ENV = {  # env var name -> (key, display name, protocol)
    "OPENAI_API_KEY": ("external:openai", "OpenAI API", "https"),
    "ANTHROPIC_API_KEY": ("external:anthropic", "Anthropic API", "https"),
    "GITHUB_TOKEN": ("external:github", "GitHub API", "https"),
    "SLACK_WEBHOOK_URL": ("external:slack", "Slack", "https"),
    "STRIPE_API_KEY": ("external:stripe", "Stripe API", "https"),
}
KNOWN_EXTERNAL_HOSTS = {"api.openai.com": ("external:openai", "OpenAI API"), "api.anthropic.com": ("external:anthropic", "Anthropic API"),
                        "api.github.com": ("external:github", "GitHub API"), "hooks.slack.com": ("external:slack", "Slack")}
CONFIG_SUFFIXES = {".conf", ".template", ".yaml", ".yml", ".toml", ".ini", ".json", ".env.example", ".cfg", ".properties"}
CONTENT_MODES = ("auto", "code", "docs")
DOC_TEXT = {".md", ".mdx", ".markdown", ".txt", ".rst", ".adoc"}
DIAGRAM_TEXT = {".mmd": "mermaid", ".mermaid": "mermaid", ".puml": "plantuml", ".plantuml": "plantuml", ".dsl": "structurizr"}
BINARY_DOCS = {".pdf", ".docx"}
ADR_PATH = re.compile(r"(^|/)(adr|adrs|decisions?)(/|$)", re.IGNORECASE)
DOC_PREFIXES = ("docs/", "doc/", "openspec/", "adr/", "architecture/")


class ComposeLoader(yaml.SafeLoader):
    """Safe loader that understands Compose's merge tags (`!reset` clears an inherited value, `!override` replaces it)."""


def _compose_tag(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
    if node.tag == "!reset":
        return None
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_scalar(node)


ComposeLoader.add_constructor("!reset", _compose_tag)
ComposeLoader.add_constructor("!override", _compose_tag)


@dataclass
class Service:
    system: str
    name: str
    key: str
    compose_file: str
    line_start: int
    line_end: int
    spec: dict[str, Any]
    context: Path | None = None
    mounts: list[Path] = field(default_factory=list)
    subtype: str = "service"
    tech: str = ""


def _rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def _service_lines(text: str) -> dict[str, tuple[int, int]]:
    try:
        node = yaml.compose(text, Loader=ComposeLoader)
    except yaml.YAMLError:
        return {}
    out: dict[str, tuple[int, int]] = {}
    if not isinstance(node, yaml.MappingNode):
        return out
    for k, v in node.value:
        if getattr(k, "value", None) == "services" and isinstance(v, yaml.MappingNode):
            for sk, sv in v.value:
                out[sk.value] = (sk.start_mark.line + 1, sv.end_mark.line + 1)
    return out


def _env_items(spec: dict[str, Any]) -> list[tuple[str, str]]:
    env = spec.get("environment") or {}
    if isinstance(env, list):
        items = []
        for e in env:
            k, _, v = str(e).partition("=")
            items.append((k, v))
        return items
    return [(str(k), "" if v is None else str(v)) for k, v in env.items()]


_VAR = re.compile(r"\$\{(?:[^{}]|\{[^{}]*\})*\}")


def _cmdline(cmd: Any) -> str:
    """A compose/Dockerfile command as one string: it may be a list (exec form) or a plain string (shell form)."""
    return cmd if isinstance(cmd, str) else " ".join(map(str, cmd or []))


def _argv(spec: dict[str, Any]) -> list[str]:
    """The process a container runs, with Docker semantics: entrypoint (compose overrides Dockerfile) + command (compose
    `command` replaces the Dockerfile CMD)."""
    df = spec.get("_df", {})

    def split(v: Any) -> list[str]:
        if isinstance(v, str):
            try:
                return shlex.split(v)
            except ValueError:
                return v.split()
        return [str(x) for x in v or []]
    entry = split(spec["entrypoint"]) if spec.get("entrypoint") is not None else df.get("entrypoint", [])
    cmd = split(spec["command"]) if spec.get("command") is not None else df.get("cmd", [])
    return entry + cmd


def console_scripts(ctx: Path) -> dict[str, str]:
    """`[project.scripts]` / `[tool.poetry.scripts]` of the build context: script name -> "module:function"."""
    f = ctx / "pyproject.toml"
    if not f.exists():
        return {}
    try:
        data = tomllib.loads(read(f))
    except tomllib.TOMLDecodeError:
        return {}
    out = dict((data.get("project") or {}).get("scripts") or {})
    out.update(((data.get("tool") or {}).get("poetry") or {}).get("scripts") or {})
    return {str(k): str(v) for k, v in out.items() if isinstance(v, str)}


def _entry_modules(argv: list[str], scripts: dict[str, str] | None = None) -> tuple[list[str], list[tuple[str, str]]]:
    """(entry modules, [(script module, sub-command)]) of a command line: `python -m pkg`, `python app.py`, `uvicorn pkg.mod:app`,
    and console scripts (`service-data query` -> the `query` command of the script's module, resolved later)."""
    mods: list[str] = []
    roles: list[tuple[str, str]] = []
    scripts = scripts or {}
    for i, c in enumerate(argv):
        if c == "-m" and i + 1 < len(argv):
            mods += [argv[i + 1], f"{argv[i + 1]}.__main__"]   # `python -m pkg` runs pkg/__main__.py
        if c.endswith(".py") and i > 0 and re.search(r"python(3(\.\d+)?)?$", argv[i - 1]):   # python path/to/script.py
            mods.append(c.removesuffix(".py").lstrip("./").replace("/", "."))
        m = re.match(r"^([A-Za-z_][\w.]*):[A-Za-z_]\w*$", c)       # uvicorn pkg.mod:app
        if m and i > 0:
            mods.append(m.group(1))
        script = scripts.get(Path(c).name)
        if script:
            module = script.split(":")[0]
            mods.append(module)
            sub = next((a for a in argv[i + 1:] if not a.startswith("-")), "")
            if sub:
                roles.append((module, sub))
    return mods, roles


def _dockerfile_info(path: Path) -> dict[str, Any]:
    txt = read(path)
    froms = re.findall(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)", txt, re.MULTILINE | re.IGNORECASE)
    def last(instr: str) -> list[str]:
        found = re.findall(rf"^\s*{instr}\s+(\[.*\]|.+)$", txt, re.MULTILINE | re.IGNORECASE)
        if not found:
            return []
        v = found[-1].strip()
        try:
            return [str(x) for x in json.loads(v)] if v.startswith("[") else shlex.split(v)
        except (ValueError, json.JSONDecodeError):
            return v.split()
    entrypoint, cmd = last("ENTRYPOINT"), last("CMD")
    expose = re.findall(r"^\s*EXPOSE\s+(.+)$", txt, re.MULTILINE | re.IGNORECASE)
    copied = []
    for cm in re.finditer(r"^\s*(?:COPY|ADD)\s+(?!--from)(?:--\S+\s+)*(.+)$", txt, re.MULTILINE | re.IGNORECASE):
        parts = shlex.split(cm.group(1)) if not cm.group(1).strip().startswith("[") else json.loads(cm.group(1))
        if len(parts) >= 2 and parts[-1] in (".", "./", "/app", "/app/", "/srv", "/code", "/src"):
            copied += [x.rstrip("/") for x in parts[:-1] if x not in (".", "./") and not any(ch in x for ch in "*?")]
    return {"base_images": froms, "entrypoint": entrypoint, "cmd": cmd, "expose": " ".join(expose).split(), "copied": copied}


class RepoAnalyzer:
    def __init__(self, root: Path, revision: str, repo_name: str, content: str = "auto"):
        if content not in CONTENT_MODES:
            raise ValueError(f"content must be one of {CONTENT_MODES}")
        self.root, self.repo, self.content = root.resolve(), repo_name, content
        self.r = ScanResult(revision=revision)
        self.files = list(walk(self.root))
        self.services: dict[str, Service] = {}         # "system/name" -> Service (a repo may hold several compose projects)
        self.by_system: dict[str, dict[str, Service]] = defaultdict(dict)

    # ------------------------------------------------------------------ orchestrate
    def run(self) -> ScanResult:
        compose_files = [f for f in self.files if re.fullmatch(r"(docker-)?compose(\.[\w\-]+)?\.ya?ml", f.name)
                         and "override" not in f.name and "coverage" not in f.name]
        if self.content == "docs":          # a documentation / architecture folder: documents, ADRs, contracts — no runtime wiring
            compose_files = []
        fragments = self._extends_fragments(compose_files)
        compose_files = [cf for cf in compose_files if cf.resolve() not in fragments]
        for cf in compose_files:
            self.compose(cf)
        if self.content != "docs":
            self.dockerfile_service()
        if self.content != "docs":
            self.persons()
            self.code()
            self.config_mounts()
        self.openapi_specs()
        self.catalog_and_owners()
        self.tables()
        self.docs()
        if self.content != "docs":
            self.code_index()
        systems = sorted(self.by_system)
        self.r.coverage = {"origin": "static", "systems": systems,
                           "prefixes": [f"container:{s}/" for s in systems] + [f"system:{s}" for s in systems] +
                                       [f"component:{s}/" for s in systems] + [f"endpoint:{s}/" for s in systems] +
                                       [f"code:{s}/" for s in systems] + [f"table:{s}/code/" for s in systems]}
        # kafka topics are only covered where the code was analyzed: declared topics absent in code are UNKNOWN, not drift
        self.r.stats = {**self.r.stats, "files": len(self.files), "compose_files": len(compose_files), "services": len(self.services),
                        "observations": len(self.r.observations), "documents": len(self.r.documents)}
        return self.r

    # ------------------------------------------------------------------ compose
    def compose(self, cf: Path) -> None:
        text = read(cf)
        try:
            data = yaml.load(text, Loader=ComposeLoader) or {}  # noqa: S506 — SafeLoader subclass
        except yaml.YAMLError as e:
            self.r.warnings.append(f"{_rel(self.root, cf)}: invalid YAML ({str(e)[:80]})")
            self.r.complete = False
            return
        self._register_project(cf, data, text)

    def dockerfile_service(self) -> None:
        """A repository without Compose services but with a root Dockerfile is one container (its own system), so its code,
        endpoints and dependencies are analyzed like any other service."""
        df = self.root / "Dockerfile"
        if self.services or not df.exists():
            return
        info = _dockerfile_info(df)
        spec: dict[str, Any] = {"build": ".", "ports": [f"{p.split('/')[0]}" for p in info.get("expose", [])], "_from_dockerfile": True}
        self._register_project(df, {"name": self.repo, "services": {self.repo: spec}}, "")

    def _register_project(self, cf: Path, data: dict, text: str) -> None:
        svcs = data.get("services") or {}
        if not isinstance(svcs, dict) or not svcs:
            return
        built = {str(v.get("image")): v.get("build") for v in svcs.values() if isinstance(v, dict) and v.get("build") and v.get("image")}
        svcs = {n: ({**v, "build": built[str(v["image"])], "_shared_image": v["image"]}
                    if isinstance(v, dict) and not v.get("build") and str(v.get("image")) in built else v) for n, v in svcs.items()}
        rel = _rel(self.root, cf)
        system = str(data.get("name") or (self.repo if cf.parent == self.root else f"{self.repo}-{cf.parent.name}"))
        lines = _service_lines(text)
        sys_key = f"system:{system}"
        self.r.node("static", sys_key, "software-system", system, V_COMPOSE,
                    attrs={"compose_file": rel, "repository": self.repo}, ref=rel, span={"path": rel, "line_start": 1})
        for name, spec in svcs.items():
            spec = self._extended(cf, svcs, spec or {})
            ls, le = lines.get(name, (1, 1))
            key = f"container:{system}/{name}"
            build = spec.get("build")
            ctx = None
            if isinstance(build, str):
                ctx = (cf.parent / build).resolve()
            elif isinstance(build, dict) and build.get("context"):
                ctx = (cf.parent / str(build["context"])).resolve()
            image = str(spec.get("image") or "")
            sub, tech = classify(image, name)
            svc = Service(system, name, key, rel, ls, le, spec, ctx, subtype=sub, tech=tech)
            for v in spec.get("volumes") or []:
                src = v.split(":")[0] if isinstance(v, str) else (v.get("source") if isinstance(v, dict) else None)
                if src and (src.startswith((".", "/"))):
                    p = (cf.parent / src).resolve()
                    if str(p).startswith(str(self.root.resolve())) and p.exists():
                        svc.mounts.append(p)
                self._volume(svc, v, rel, ls)
            df_info = {}
            if ctx and ctx.exists():
                df = ctx / (build.get("dockerfile", "Dockerfile") if isinstance(build, dict) else "Dockerfile")
                if df.exists():
                    df_info = _dockerfile_info(df)
                    svc.spec = {**spec, "_dockerfile": _rel(self.root, df), "_df": df_info}
                    if not tech:
                        s2, t2 = classify(" ".join(df_info.get("base_images", [])))
                        if t2:
                            svc.subtype, svc.tech = s2, t2
            if not svc.tech and ctx and (ctx / "package.json").exists() and (ctx / "index.html").exists():
                svc.subtype, svc.tech = "webapp", "Single-page web app"
            elif not svc.tech and ctx and ((ctx / "pyproject.toml").exists() or (ctx / "requirements.txt").exists()):
                svc.tech = "Python service"
            ports = [str(p) for p in spec.get("ports") or []]
            attrs = {"image": image, "subtype": svc.subtype, "technology": svc.tech, "compose_file": rel,
                     "build_context": _rel(self.root, ctx) if ctx else "", "ports": ports,
                     "profiles": spec.get("profiles") or [], "networks": sorted(spec.get("networks") or [])
                     if isinstance(spec.get("networks"), list) else sorted((spec.get("networks") or {}).keys()),
                     "container_name": str(spec.get("container_name") or ""), "optional": bool(spec.get("profiles")),
                     "one_shot": str(spec.get("restart", "")) == "no"}
            if df_info:
                attrs["base_images"] = df_info.get("base_images", [])
            self.r.node("static", key, "container", name, V_COMPOSE, attrs=attrs, ref=rel,
                        span={"path": rel, "line_start": ls, "line_end": le})
            self.r.edge("static", sys_key, "contains", key, V_COMPOSE, ref=rel, span={"path": rel, "line_start": ls})
            self.services[f"{svc.system}/{name}"] = svc
            self.by_system[system][name] = svc
        # wiring (second pass: every service name of this system is known)
        self._conf_override = None
        for name, svc in self.by_system[system].items():
            spec = svc.spec
            span = {"path": rel, "line_start": svc.line_start, "line_end": svc.line_end}
            deps = spec.get("depends_on") or []
            for d in (deps.keys() if isinstance(deps, dict) else deps):
                if d in self.by_system[system]:
                    cond = deps[d].get("condition", "") if isinstance(deps, dict) and isinstance(deps[d], dict) else ""
                    self.r.edge("static", svc.key, "depends-on", self.by_system[system][d].key, V_COMPOSE, ref=rel, span=span,
                                attrs={"condition": cond, "protocol": ""})
            for k, v in _env_items(spec):
                self._wire_value(svc, v, rel, span, var=k)
                if k in KNOWN_EXTERNAL_ENV and v and "..." not in v:
                    ek, en, proto = KNOWN_EXTERNAL_ENV[k]
                    self.r.node("inferred", ek, "external-system", en, V_INFER, attrs={"evidence": f"{k} configured"}, ref=rel,
                                span=span, confidence=0.6)
                    self.r.edge("inferred", svc.key, "calls", ek, V_INFER, attrs={"protocol": proto, "via": k}, ref=rel,
                                span=span, confidence=0.6)

    def _extends_fragments(self, compose_files: list[Path]) -> set[Path]:
        """Compose files only used as `extends: {file: ...}` bases: merged into the extending service, never a system."""
        frags: set[Path] = set()
        for cf in compose_files:
            text = read(cf)
            for m in re.finditer(r"^\s+file:\s*['\"]?([^'\"\n]+)", text, re.MULTILINE):
                if "extends" not in text:
                    continue
                pattern = re.sub(r"\$\{[^}]*\}", "*", m.group(1).strip())
                frags |= {f.resolve() for f in cf.parent.glob(pattern)}
        return frags - {cf.resolve() for cf in compose_files if "extends" in read(cf)}

    def _extended(self, cf: Path, svcs: dict, spec: dict) -> dict:
        """Compose `extends`: the base service (same file or another file) merged under this service's own keys."""
        ext = spec.get("extends")
        if not isinstance(ext, dict | str):
            return spec
        base_name = ext if isinstance(ext, str) else ext.get("service")
        base: dict = {}
        if isinstance(ext, dict) and ext.get("file"):
            f = (cf.parent / str(ext["file"]).replace("${DEVICE:-cpu}", "cpu")).resolve()
            f = f if f.exists() else next(iter(sorted(f.parent.glob(re.sub(r"\$\{[^}]*\}", "*", f.name)))), f) if f.parent.exists() else f
            if f.exists():
                try:
                    base = ((yaml.load(read(f), Loader=ComposeLoader) or {}).get("services") or {}).get(base_name) or {}  # noqa: S506
                except yaml.YAMLError:
                    base = {}
        elif base_name in svcs:
            base = svcs[base_name] or {}
        merged = {**base, **{k: v for k, v in spec.items() if k != "extends"}}
        if isinstance(base.get("build"), dict) and isinstance(spec.get("build"), str):
            merged["build"] = {**base["build"], "context": spec["build"]}
        merged["_extends"] = f"{(ext.get('file') + ':') if isinstance(ext, dict) and ext.get('file') else ''}{base_name}"
        return merged

    def _volume(self, svc: Service, v: Any, rel: str, line: int) -> None:
        """Data volumes (named volumes and host directories, not single config files) become storage elements."""
        if isinstance(v, str):
            parts = _VAR.sub("VAR", v).split(":")                # ${A:-${B}} contains colons: mask variables before splitting
            if len(parts) < 2:
                return
            src, dst, mode = parts[0], parts[1], (parts[2] if len(parts) > 2 else "rw")
            src = "host path" if src == "VAR" else src
        elif isinstance(v, dict) and v.get("target"):
            src, dst, mode = str(v.get("source", "")), str(v["target"]), "ro" if v.get("read_only") else "rw"
        else:
            return
        if not dst.startswith("/") or Path(dst.rstrip("/")).suffix:       # a mounted FILE (config, script, schema) is not a data store
            return
        if dst in ("/var/run/docker.sock", "/etc/localtime"):
            return
        name = dst.rstrip("/").rsplit("/", 1)[-1] or dst
        key = f"container:{svc.system}/volume-{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}"
        kind = "named volume" if src and not src.startswith((".", "/", "$", "~")) else "host folder"
        self.r.node("static", key, "container", f"{name} ({kind})", V_COMPOSE, ref=rel, span={"path": rel, "line_start": line},
                    attrs={"subtype": "storage", "technology": kind, "volume": True, "mount_path": dst, "source": src[:200]})
        self.r.edge("static", f"system:{svc.system}", "contains", key, V_COMPOSE, ref=rel)
        self.r.edge("static", svc.key, "reads" if mode.startswith("ro") else "writes", key, V_COMPOSE, ref=rel,
                    span={"path": rel, "line_start": line}, attrs={"protocol": "filesystem", "mount": dst, "mode": mode}, confidence=0.9)

    def _wire_value(self, svc: Service, value: str, ref: str, span: dict, var: str = "") -> None:
        names = self.by_system[svc.system]
        found = False
        for m in URL_RX.finditer(value):
            host, scheme = m.group("host"), scheme_base(m.group("scheme"))
            port = m.group("port") or ""
            if host in names and host != svc.name:
                rel, proto = SCHEME_REL.get(scheme, ("calls", scheme))
                attrs = {"protocol": proto, "port": port, "via": var or "config", "url": safe_url(m.group(0))[:200]}
                if rel == "writes":
                    attrs["access"] = "read-write (inferred from connection URL)"
                conf = getattr(self, "_conf_override", None) or (0.9 if rel == "calls" else 0.8)
                if getattr(self, "_conf_override", None):
                    attrs["shared_build_context"] = True
                self.r.edge("static", svc.key, rel, names[host].key, V_CONFIG, attrs=attrs, ref=ref, span=span, confidence=conf)
                found = True
            elif host in KNOWN_EXTERNAL_HOSTS:
                ek, en = KNOWN_EXTERNAL_HOSTS[host]
                self.r.node("static", ek, "external-system", en, V_CONFIG, attrs={"host": host}, ref=ref, span=span)
                self.r.edge("static", svc.key, "calls", ek, V_CONFIG, attrs={"protocol": scheme, "via": var or "config"},
                            ref=ref, span=span, confidence=0.9)
                found = True
            elif host != svc.name and (nr := name_ref(host)):      # maybe a service of another repository / datasource
                rel, proto = SCHEME_REL.get(scheme, ("calls", scheme))
                self.r.edge("static", svc.key, rel, nr, V_XREPO, attrs={"protocol": proto, "port": port, "via": var or "config",
                            "url": safe_url(m.group(0))[:200], "resolved_by": "name"}, ref=ref, span=span, confidence=0.7)
                found = True
        if not found:
            hm = HOSTPORT_RX.match(value.strip())
            if hm and hm.group("host") in names and hm.group("host") != svc.name:
                self.r.edge("static", svc.key, "calls", names[hm.group("host")].key, V_CONFIG,
                            attrs={"protocol": "tcp", "port": hm.group("port"), "via": var or "config"}, ref=ref, span=span,
                            confidence=0.85)
            elif hm and hm.group("host") != svc.name and (nr := name_ref(hm.group("host"))):
                self.r.edge("static", svc.key, "calls", nr, V_XREPO, attrs={"protocol": "tcp", "port": hm.group("port"),
                            "via": var or "config", "resolved_by": "name"}, ref=ref, span=span, confidence=0.65)

    def persons(self) -> None:
        """Containers published on all host interfaces with a UI/IdP role are reached by end users (inferred)."""
        for svc in self.services.values():
            public = [p for p in (svc.spec.get("ports") or []) if isinstance(p, str | int) and not str(p).startswith("127.0.0.1")]
            if public and svc.subtype in ("webapp", "identity"):
                self.r.node("inferred", "person:user", "person", "User", V_INFER, attrs={"description": "Person using the system"},
                            confidence=0.5)
                self.r.edge("inferred", "person:user", "calls", svc.key, V_INFER,
                            attrs={"protocol": "https", "ports": [str(p) for p in public]}, ref=svc.compose_file,
                            span={"path": svc.compose_file, "line_start": svc.line_start}, confidence=0.5)

    # ------------------------------------------------------------------ code inside build contexts
    def code(self) -> None:
        by_ctx: dict[Path, list[Service]] = defaultdict(list)
        for s in self.services.values():
            if s.context and s.context.exists():
                by_ctx[s.context].append(s)
        for ctx, svcs in by_ctx.items():
            ctx_files = [f for f in self.files if str(f).startswith(str(ctx) + "/")]
            self.manifests(ctx, ctx_files, svcs)
            if any(f.suffix == ".py" for f in ctx_files):
                self.python(ctx, ctx_files, svcs)
            if (ctx / "package.json").exists():
                self.typescript(ctx, ctx_files, svcs)
            self.web_ui(ctx, ctx_files, svcs)
            for f in ctx_files:            # config files inside the context (e.g. nginx templates)
                rel_parts = f.relative_to(self.root).parts
                if f.suffix in CONFIG_SUFFIXES and f.stat().st_size < 200_000 and not {"test", "tests"} & set(rel_parts):
                    for s in svcs:
                        # several services share this image: which one reads the file is unknown -> low confidence
                        self._scan_config(s, f, confidence=0.4 if len(svcs) > 1 else None)

    def python(self, ctx: Path, files: list[Path], svcs: list[Service]) -> None:
        errors: list[str] = []
        declared = gateway_maps.declared_endpoints(ctx, files)
        routes = gateway_maps.routing_tables(ctx, files) if len(svcs) == 1 else []
        # handlers loaded by name from configuration: entries of the only service, or (shared image) of every role that runs
        # the handler's component
        dynamic_entries = sorted({d.module for d in declared if d.module}) if len(svcs) == 1 else []
        scripts = console_scripts(ctx)
        entries_all = [e for s in svcs for e in _entry_modules(_argv(s.spec), scripts)[0]] + dynamic_entries
        copied = [c for s in svcs for c in s.spec.get("_df", {}).get("copied", [])]
        roots = python_code.package_roots(ctx, files, entries_all, copied)
        mods = python_code.analyze(ctx, files, errors, roots)
        if errors:
            self.r.complete = False          # unparsed modules: their evidence is UNKNOWN, so this scan must not tombstone
            self.r.warnings += [f"python parse failed (module skipped): {e}" for e in errors[:20]]
        if not mods:
            return
        for s in svcs:
            entries, roles = _entry_modules(_argv(s.spec), scripts)
            role_mods = [m for mod, sub in roles for m in python_code.role_entries(mods, mod, sub)]
            entries = (role_mods or entries) + dynamic_entries                 # a CLI role runs only what its command starts
            reach = python_code.reachable(mods, entries) if entries else set()
            if len(svcs) > 1 and declared and reach:
                running = {python_code.component_of(m) for m in reach}
                handlers = sorted({d.module for d in declared if d.module in mods and python_code.component_of(d.module) in running})
                reach |= python_code.reachable(mods, handlers)
            if entries and not reach:
                continue
            if not entries:
                if len(svcs) > 1:
                    continue           # shared image without a known entrypoint: do not guess which code runs here
                reach = set(mods)
            comps: dict[str, list[str]] = defaultdict(list)
            for m in reach:
                if m.count(".") >= 1 and not m.split(".")[-1].startswith("test"):
                    comps[python_code.component_of(m)].append(m)
            for comp, members in sorted(comps.items()):
                f = mods[comp].path if comp in mods else mods[min(members)].path
                rel = _rel(self.root, f.parent if f.name == "__init__.py" else f)
                ck = f"component:{s.system}/{s.name}/{comp}"
                self.r.node("static", ck, "component", comp.split(".", 1)[-1], python_code.PARSER_VERSION,
                            attrs={"module": comp, "modules": len(members), "language": "python", "path": rel,
                                   "entrypoints": entries}, ref=rel, span={"path": rel})
                self.r.edge("static", s.key, "contains", ck, python_code.PARSER_VERSION, ref=rel, span={"path": rel})
            dep_counts: dict[tuple[str, str], int] = defaultdict(int)
            for m in reach:
                for imp in mods[m].imports:
                    a, b = python_code.component_of(m), python_code.component_of(imp)
                    if a != b and a in comps and b in comps:
                        dep_counts[(a, b)] += 1
            for (a, b), n in sorted(dep_counts.items()):
                self.r.edge("static", f"component:{s.system}/{s.name}/{a}", "depends-on", f"component:{s.system}/{s.name}/{b}",
                            python_code.PARSER_VERSION, attrs={"imports": n, "protocol": "in-process"},
                            ref=_rel(self.root, mods[a].path) if a in mods else "", confidence=1.0)
            self._code_elements(s, mods, reach, comps)
            self._resources(s, mods, reach)
            self._http_calls(s, mods, reach)
            self._kafka(s, mods, reach)
            cmdline = _cmdline(_argv(s.spec))
            starts_server = any(i.split(".")[0] in ("uvicorn", "gunicorn", "hypercorn", "granian", "daphne") for m in reach for i in mods[m].external_imports)
            role_server = any(python_code.role_starts_server(mods, mod, sub) for mod, sub in roles)
            serves_http = bool(re.search(r"uvicorn|gunicorn|hypercorn|granian|flask\s+run|daphne", cmdline)) or starts_server or role_server
            for m in sorted(reach) if serves_http else []:
                for rt in mods[m].routes:
                    self._endpoint(s, mods, comps, rt.method, rt.path, m, rt.handler, _rel(self.root, Path(rt.file)), rt.line, python_code.PARSER_VERSION)
            for d in declared:
                if len(svcs) > 1 and d.module not in reach:
                    continue                                   # this role does not run that handler
                m = d.module if d.module in mods else ""
                self._endpoint(s, mods, comps, d.method, d.path, m, d.handler, d.source, d.line, gateway_maps.V_DECLARED, {"declared_in": d.source})
            self._gateway_routes(s, mods, comps, routes, declared)

    def _endpoint(self, s: Service, mods: dict, comps: dict, method: str, path: str, module: str, handler: str, rel: str, line: int,
                  parser: str, extra: dict | None = None) -> str:
        """One HTTP endpoint of a service, with the components its module uses and the resources it touches (for flows)."""
        ek = f"endpoint:{s.system}/{s.name}/{method} {path}"
        attrs: dict[str, Any] = {"method": method, "path": path, "handler": handler, "module": module, **(extra or {})}
        if module:
            own = python_code.component_of(module)
            attrs["component"] = f"component:{s.system}/{s.name}/{own}"
            attrs["uses"] = sorted({f"component:{s.system}/{s.name}/{python_code.component_of(i)}" for i in mods[module].imports
                                    if python_code.component_of(i) != own and python_code.component_of(i) in comps})
            attrs["resources"] = sorted({res.key.format(system=s.system, service=s.name)
                                         for res, _ in resources.resources_for(mods[module].external_imports, mods[module].source)})
        self.r.node("static", ek, "api-endpoint", f"{method} {path}", parser, attrs=attrs, ref=rel, span={"path": rel, "line_start": line, "line_end": line})
        self.r.edge("static", s.key, "exposes", ek, parser, ref=rel, span={"path": rel, "line_start": line})
        return ek

    def _gateway_routes(self, s: Service, mods: dict, comps: dict, routes: list, declared: list) -> None:
        """An API gateway's routing table: every action becomes an endpoint of this service that calls the backend endpoint
        (`name:<host>#<METHOD> <path>`, resolved across datasources by the graph builder)."""
        if not routes:
            return
        tables = {r.source.rsplit("/", 1)[-1] for r in routes}
        dispatchers = [d for d in declared if d.module in mods and any(t in mods[d.module].source for t in tables)]
        module = dispatchers[0].module if dispatchers else ""
        via = dispatchers[0].path if dispatchers else ""
        hop = next((c for c in (mods[module].http_calls if module else []) if c.path), None)     # e.g. presenter -> gate /gate/action_sync
        hop_ref = f"name:{hop.service}#{hop.method} {hop.path}" if hop else ""
        hosts: dict[str, int] = defaultdict(int)
        for rt in routes:
            host = gateway_maps.host_name(rt.host)
            ak = self._endpoint(s, mods, comps, "ACTION", rt.action, module, "", rt.source, rt.line, gateway_maps.V_ROUTES,
                                {"dispatcher": via, "roles": rt.roles, "description": rt.description, "routes_to": f"{rt.host} {rt.method} {rt.path}",
                                 **({"forwarded_by": f"{hop.service} {hop.method} {hop.path}"} if hop else {})})
            if not host:
                continue                                       # local/dev target: not a resolvable service
            hosts[host] += 1
            self.r.edge("static", ak, "calls", f"name:{host}#{rt.method} {rt.path}", gateway_maps.V_ROUTES, ref=rt.source,
                        span={"path": rt.source, "line_start": rt.line}, confidence=0.85,
                        attrs={"protocol": "http", "method": rt.method, "path": rt.path, "action": rt.action, "resolved_by": "name",
                               **({"via": hop_ref} if hop_ref else {})})
        for host, n in hosts.items():
            self.r.edge("static", s.key, "calls", f"name:{host}", gateway_maps.V_ROUTES, attrs={"protocol": "http", "routes": n, "resolved_by": "name"},
                        confidence=0.85)

    def _http_calls(self, s: Service, mods: dict, reach: set[str]) -> None:
        """Outgoing HTTP calls to other services (host literal or config variable): component -> `name:<svc>#<METHOD> <path>`,
        resolved by the graph builder to the service's endpoint in any datasource; the container rolls the call up."""
        seen: set[tuple[str, str]] = set()
        for m in sorted(reach):
            for c in mods[m].http_calls:
                if c.service in self.by_system.get(s.system, {}) and c.service != s.name:
                    continue                                       # same-compose services are wired from configuration already
                rel = _rel(self.root, mods[m].path)
                target = f"name:{c.service}#{c.method} {c.path}" if c.path else f"name:{c.service}"
                comp = f"component:{s.system}/{s.name}/{python_code.component_of(m)}"
                attrs = {"protocol": "http", "method": c.method, "path": c.path, "via": c.via[:120], "resolved_by": "name", "module": m}
                self.r.edge("static", comp, "calls", target, V_XREPO, attrs=attrs, ref=rel, span={"path": rel, "line_start": c.line}, confidence=0.8)
                if (c.service, "") not in seen:
                    seen.add((c.service, ""))
                    self.r.edge("static", s.key, "calls", f"name:{c.service}", V_XREPO, ref=rel, span={"path": rel, "line_start": c.line},
                                attrs={"protocol": "http", "via": c.via[:120], "resolved_by": "name"}, confidence=0.8)

    def _resources(self, s: Service, mods: dict, reach: set[str]) -> None:
        """What each component uses (SaaS APIs, embedded databases, stores, ML runtimes, external tools), from its imports."""
        rolled: dict[str, tuple[str, str]] = {}
        for m in sorted(reach):
            mod = mods[m]
            comp_key = f"component:{s.system}/{s.name}/{python_code.component_of(m)}"
            rel = _rel(self.root, mod.path)
            for res, hint in resources.resources_for(mod.external_imports, mod.source):
                key = res.key.format(system=s.system, service=s.name)
                top = hint.split()[-1]
                span = {"path": rel, "line_start": resources.import_line(mod.source, top)}
                self.r.node("static", key, res.kind, res.name, resources.V_RESOURCES, ref=rel, span=span,
                            attrs={"subtype": res.subtype, "technology": res.technology, "used_by": m})
                if res.kind == "component":
                    self.r.edge("static", s.key, "contains", key, resources.V_RESOURCES, ref=rel)
                if key != comp_key:
                    self.r.edge("static", comp_key, res.relation, key, resources.V_RESOURCES, ref=rel, span=span,
                                attrs={"protocol": res.protocol, "via": hint, "module": m}, confidence=0.85)
                if res.kind != "component":
                    rolled.setdefault(key, (res.relation, res.protocol))
        for key, (rel_kind, proto) in rolled.items():           # container-level rollup for L1/L2
            self.r.edge("static", s.key, rel_kind, key, resources.V_RESOURCES, attrs={"protocol": proto, "rollup": "from components"},
                        confidence=0.85)

    def web_ui(self, ctx: Path, files: list[Path], svcs: list[Service]) -> None:
        """A SPA in the build context is the container's Web UI component; its /api calls are matched to the endpoints."""
        if len(svcs) != 1:
            return                                        # shared build context: which container serves the UI is unknown
        s = svcs[0]
        endpoints: dict[str, list[str]] = defaultdict(list)
        for o in self.r.observations:
            if o.kind == "api-endpoint" and o.subject_key.startswith(f"endpoint:{s.system}/{s.name}/") and o.subject_key not in endpoints[webui.normalize(o.attributes["path"])]:
                endpoints[webui.normalize(o.attributes["path"])].append(o.subject_key)
        for ui in webui.find_uis(ctx, files):
            if ui.root.resolve() == ctx.resolve():        # the container IS the UI (already a webapp container): no extra component
                self._rpc_calls(s, webui.scan_rpc(ui, files), None)
                continue
            webui.scan_calls(ui, files)
            webui.scan_rpc(ui, files)
            key = f"component:{s.system}/{s.name}/web-ui"
            rel = _rel(self.root, ui.root / "package.json")
            self.r.node("static", key, "component", f"Web UI ({ui.framework})", webui.V_WEBUI, ref=rel, span={"path": rel},
                        attrs={"subtype": "webapp", "technology": ui.framework, "path": _rel(self.root, ui.root), "api_calls": len(ui.calls)})
            self.r.edge("static", s.key, "contains", key, webui.V_WEBUI, ref=rel)
            self.r.node("inferred", "person:user", "person", "User", V_INFER, attrs={"description": "Person using the system"}, confidence=0.6)
            self.r.edge("inferred", "person:user", "calls", key, V_INFER, attrs={"protocol": "https"}, ref=rel, confidence=0.6)
            for call, where in sorted(ui.calls.items()):
                targets = webui.match_endpoints(call, endpoints)
                f, line = where[0]
                frel = _rel(self.root, Path(f))
                for ek in targets:
                    self.r.edge("static", key, "calls", ek, webui.V_WEBUI, attrs={"protocol": "https", "path": call, "call_sites": len(where)},
                                ref=frel, span={"path": frel, "line_start": line}, confidence=0.85 if len(targets) == 1 else 0.7)
            self._rpc_calls(s, ui, key)

    def _rpc_calls(self, s: Service, ui: webui.WebUi, ui_key: str | None) -> None:
        """RPC actions the UI sends to a backend named by its env var: the feature module that sends each action calls
        `action:<name>@<service>` (resolved by the graph builder to the gateway's ACTION endpoint in any datasource)."""
        t = webui.primary_transport(ui)
        if not t:
            return
        src = ui.root / "src"
        trel = _rel(self.root, Path(t.file))
        hop = f"name:{t.service}#POST {t.path}" if t.path else f"name:{t.service}"
        self.r.node("inferred", "person:user", "person", "User", V_INFER, attrs={"description": "Person using the system"}, confidence=0.6)
        self.r.edge("inferred", "person:user", "calls", s.key, V_INFER, attrs={"protocol": "https"}, ref=trel, confidence=0.6)
        self.r.edge("static", s.key, "calls", hop, webui.V_WEBUI, ref=trel, span={"path": trel, "line_start": t.line},
                    attrs={"protocol": "https", "via_env": t.env, "transport": "rpc", "resolved_by": "name"}, confidence=0.8)
        seen: set[tuple[str, str]] = set()
        for a in ui.actions:
            f = Path(a.file)
            if ui_key:
                comp = ui_key
            else:
                try:
                    parts = f.relative_to(src).parts
                    comp = f"component:{s.system}/{s.name}/{parts[0] if len(parts) > 1 else 'app'}"
                except ValueError:
                    comp = s.key
            if (comp, a.action) in seen:
                continue
            seen.add((comp, a.action))
            frel = _rel(self.root, f)
            self.r.edge("static", comp, "calls", f"action:{a.action}@{t.service}", webui.V_WEBUI, ref=frel,
                        span={"path": frel, "line_start": a.line},
                        attrs={"protocol": "https", "method": "ACTION", "path": a.action, "action": a.action, "via_env": t.env,
                               "resolved_by": "name"}, confidence=0.8)

    MAX_CODE_PER_COMPONENT = 60
    MAX_CODE_PER_SERVICE = 1500

    def _code_elements(self, s: Service, mods: dict, reach: set[str], comps: dict[str, list[str]]) -> None:
        """C4 L4: public top-level classes and functions per component, with inheritance and `uses` references between them
        (resolved through the module's imports; unresolved names are ignored, never guessed)."""
        fq: dict[str, tuple[str, Any]] = {}                       # "pkg.mod.Name" -> (module, CodeDef)
        for m in reach:
            for d in mods[m].defs:
                if not d.name.startswith("_"):
                    fq[f"{m}.{d.name}"] = (m, d)
        chosen: set[str] = set()
        total = 0
        for comp, members in sorted(comps.items()):
            defs = [(f"{m}.{d.name}", m, d) for m in sorted(members) for d in mods[m].defs if not d.name.startswith("_")]
            defs.sort(key=lambda x: (x[2].kind != "class", -len(x[2].refs), x[0]))
            for name, m, d in defs[: self.MAX_CODE_PER_COMPONENT]:
                if total >= self.MAX_CODE_PER_SERVICE:
                    self.r.warnings.append(f"{s.name}: L4 code element limit ({self.MAX_CODE_PER_SERVICE}) reached")
                    break
                rel = _rel(self.root, mods[m].path)
                k = f"code:{s.system}/{s.name}/{name}"
                self.r.node("static", k, "code", d.name, python_code.PARSER_VERSION, ref=rel,
                            span={"path": rel, "line_start": d.line_start, "line_end": d.line_end},
                            attrs={"element": d.kind, "module": m, "path": rel, "line_start": d.line_start, "line_end": d.line_end,
                                   "bases": d.bases[:10], "methods": d.methods, "async": d.is_async, "language": "python",
                                   "method_list": [{"name": mn, "line": ml} for mn, ml in d.method_list[:80]],
                                   "technology": f"python {d.kind}"})
                self.r.edge("static", f"component:{s.system}/{s.name}/{comp}", "contains", k, python_code.PARSER_VERSION, ref=rel)
                chosen.add(name)
                total += 1
        for name in sorted(chosen):
            m, d = fq[name]
            local = mods[m].names
            seen = 0
            base_names = {b.split(".")[-1] for b in d.bases}
            for ref in sorted(d.refs | base_names):
                tgt = f"{m}.{ref}" if f"{m}.{ref}" in fq else local.get(ref)
                if not tgt or tgt == name or tgt not in chosen:
                    continue
                rel = _rel(self.root, mods[m].path)
                self.r.edge("static", f"code:{s.system}/{s.name}/{name}", "depends-on", f"code:{s.system}/{s.name}/{tgt}", python_code.PARSER_VERSION,
                            attrs={"relation": "inherits" if ref in {b.split('.')[-1] for b in d.bases} else "uses", "protocol": "in-process"},
                            ref=rel, span={"path": rel, "line_start": d.line_start, "line_end": d.line_end}, confidence=0.9)
                seen += 1
                if seen >= 15:
                    break

    def _broker_for(self, s: Service) -> Service | None:
        """The Kafka broker this service is configured to use (bootstrap host in its environment)."""
        names = self.by_system[s.system]
        for _, v in _env_items(s.spec):
            hosts = [m.group("host") for m in URL_RX.finditer(v)]
            for part in v.split(","):
                hm = HOSTPORT_RX.match(part.strip())
                if hm:
                    hosts.append(hm.group("host"))
            for h in hosts:
                b = names.get(h)
                if b and b is not s and re.search(r"kafka|redpanda", f"{b.name} {b.spec.get('image', '')}", re.IGNORECASE):
                    return b
        return None

    def _kafka(self, s: Service, mods: dict, reach: set[str]) -> None:
        uses = [(m, u) for m in sorted(reach) for u in mods[m].kafka]
        if not uses:
            return
        broker = self._broker_for(s)
        if broker is None:
            self.r.warnings.append(f"{s.name}: Kafka usage found but no broker in its configuration; topics left UNKNOWN")
            return
        groups = sorted({u.topic for _, u in uses if u.direction == "group"})
        base = f"{s.system}/{broker.name}"
        for m, u in uses:
            if u.direction == "group":
                continue
            rel = _rel(self.root, mods[m].path)
            tk = f"kafka-topic:{base}/{u.topic}"
            span = {"path": rel, "line_start": u.line, "line_end": u.line}
            self.r.node("static", tk, "kafka-topic", u.topic, python_code.PARSER_VERSION, attrs={"technology": "Kafka topic"}, ref=rel, span=span)
            self.r.edge("static", broker.key, "contains", tk, python_code.PARSER_VERSION, ref=rel, span=span)
            attrs = {"protocols": ["kafka"], "module": m}
            if u.direction == "consumes" and groups:
                attrs["group"] = groups[0] if len(groups) == 1 else groups
            self.r.edge("static", s.key, u.direction, tk, python_code.PARSER_VERSION, attrs=attrs, ref=rel, span=span, confidence=0.95)

    def typescript(self, ctx: Path, files: list[Path], svcs: list[Service]) -> None:
        src = ctx / "src"
        if not src.exists():
            return
        comps: dict[str, int] = defaultdict(int)
        deps: dict[tuple[str, str], int] = defaultdict(int)
        imp_rx = re.compile(r"""(?:from|import)\s*\(?\s*['"]([^'"]+)['"]""")
        for f in files:
            if f.suffix not in (".ts", ".tsx", ".js", ".jsx") or not str(f).startswith(str(src) + "/"):
                continue
            parts = f.relative_to(src).parts
            comp = parts[0] if len(parts) > 1 else "app"
            comps[comp] += 1
            for spec in imp_rx.findall(read(f)):
                target = None
                if spec.startswith("@/"):
                    target = spec[2:].split("/")[0]
                elif spec.startswith("."):
                    try:
                        rp = (f.parent / spec).resolve().relative_to(src.resolve()).parts
                        target = rp[0] if len(rp) > 1 else "app"
                    except ValueError:
                        target = None
                if target and target != comp:
                    deps[(comp, target)] += 1
        for s in svcs:
            for comp, n in sorted(comps.items()):
                ck = f"component:{s.system}/{s.name}/{comp}"
                rel = _rel(self.root, src / comp)
                self.r.node("static", ck, "component", comp, V_TS, attrs={"files": n, "language": "typescript", "path": rel},
                            ref=rel, span={"path": rel})
                self.r.edge("static", s.key, "contains", ck, V_TS, ref=rel)
            for (a, b), n in sorted(deps.items()):
                if a in comps and b in comps:
                    self.r.edge("static", f"component:{s.system}/{s.name}/{a}", "depends-on",
                                f"component:{s.system}/{s.name}/{b}", V_TS, attrs={"imports": n, "protocol": "in-process"})

    def manifests(self, ctx: Path, files: list[Path], svcs: list[Service]) -> None:
        libs: list[tuple[str, str, str, str]] = []      # (ecosystem, name, spec, file)
        pp = ctx / "pyproject.toml"
        if pp.exists():
            try:
                data = tomllib.loads(read(pp))
                for d in data.get("project", {}).get("dependencies", []):
                    m = re.match(r"^\s*([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(.*)$", d)
                    if m:
                        libs.append(("pypi", m.group(1).lower(), m.group(3).strip(), _rel(self.root, pp)))
            except tomllib.TOMLDecodeError:
                self.r.warnings.append(f"{_rel(self.root, pp)}: invalid TOML")
        rq = ctx / "requirements.txt"
        if rq.exists():
            for line in read(rq).splitlines():
                m = re.match(r"^\s*([A-Za-z0-9_.\-]+)\s*([<>=!~].*)?$", line)
                if m and not line.strip().startswith("#"):
                    libs.append(("pypi", m.group(1).lower(), (m.group(2) or "").strip(), _rel(self.root, rq)))
        pj = ctx / "package.json"
        if pj.exists():
            try:
                data = json.loads(read(pj))
                for name, ver in sorted((data.get("dependencies") or {}).items()):
                    libs.append(("npm", name, str(ver), _rel(self.root, pj)))
            except json.JSONDecodeError:
                self.r.warnings.append(f"{_rel(self.root, pj)}: invalid JSON")
        for eco, name, spec, f in libs:
            lk = f"library:{eco}/{name}"
            self.r.node("static", lk, "library", name, V_MANIFEST, attrs={"ecosystem": eco}, ref=f, span={"path": f})
            for s in svcs:
                self.r.edge("static", s.key, "depends-on", lk, V_MANIFEST, attrs={"version": spec, "protocol": "library"},
                            ref=f, span={"path": f})

    # ------------------------------------------------------------------ mounted config files
    def _scan_config(self, svc: Service, f: Path, confidence: float | None = None) -> None:
        rel = _rel(self.root, f)
        self._conf_override = confidence
        for i, line in enumerate(read(f).splitlines(), 1):
            s = line.strip()
            if not s or s.startswith(("#", "//", ";")):
                continue
            s = s.split(" #", 1)[0]
            if "://" in s or re.search(r"\b\w+:\d{2,5}\b", s):
                for tok in re.findall(r"[A-Za-z][\w+.\-]*://[^\s\"',;]+|\b[A-Za-z][\w.\-]*:\d{2,5}\b", s):
                    self._wire_value(svc, tok, rel, {"path": rel, "line_start": i, "line_end": i}, var=rel)
            if re.search(r"\bopenai/[\w.\-*]+", s):
                self.r.node("static", "external:openai", "external-system", "OpenAI API", V_CONFIG,
                            attrs={"evidence": "OpenAI model route in gateway config"}, ref=rel, span={"path": rel, "line_start": i})
                self.r.edge("static", svc.key, "calls", "external:openai", V_CONFIG, attrs={"protocol": "https", "via": rel},
                            ref=rel, span={"path": rel, "line_start": i}, confidence=0.9)

    def config_mounts(self) -> None:
        self._conf_override = None
        for svc in self.services.values():
            for m in svc.mounts:
                targets = [m] if m.is_file() else [f for f in self.files if str(f).startswith(str(m) + "/")]
                for f in targets[:50]:
                    if f.suffix in CONFIG_SUFFIXES or f.suffix == "":
                        self._scan_config(svc, f)

    # ------------------------------------------------------------------ OpenAPI / AsyncAPI documents in the repo
    def openapi_specs(self) -> None:
        for f in self.files:
            if f.suffix not in (".yaml", ".yml", ".json") or f.stat().st_size > 800_000:
                continue
            head = read(f)[:400]
            if not re.search(r"^\s*[\"']?(openapi|asyncapi)[\"']?\s*:", head, re.MULTILINE):
                continue
            try:
                data = yaml.safe_load(read(f)) if f.suffix != ".json" else json.loads(read(f))
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(data, dict):
                continue
            rel = _rel(self.root, f)
            title = str((data.get("info") or {}).get("title") or f.stem)
            owner = self._owner_service(f)
            sysname = owner.system if owner else self.repo
            ck = f"contract:{sysname}/{rel}"
            kind = "asyncapi" if "asyncapi" in data else "openapi"
            self.r.node("static", ck, "api-contract", title, V_OPENAPI, attrs={"format": kind, "version": str((data.get("info") or {}).get("version", "")),
                        "path": rel}, ref=rel, span={"path": rel})
            if owner:
                self.r.edge("static", owner.key, "implements", ck, V_OPENAPI, ref=rel, confidence=0.8)
            for p, ops in (data.get("paths") or {}).items():
                for meth in (ops or {}):
                    if meth.lower() in ("get", "post", "put", "patch", "delete", "head", "options"):
                        ek = f"endpoint:{sysname}/{owner.name if owner else 'contract'}/{meth.upper()} {p}"
                        self.r.node("static", ek, "api-endpoint", f"{meth.upper()} {p}", V_OPENAPI,
                                    attrs={"method": meth.upper(), "path": p, "contract": rel, "declared": True}, ref=rel, span={"path": rel})
                        self.r.edge("static", ck, "contains", ek, V_OPENAPI, ref=rel)

    def _owner_service(self, f: Path) -> Service | None:
        best = None
        for s in self.services.values():
            if s.context and str(f).startswith(str(s.context) + "/") and (best is None or len(str(s.context)) > len(str(best.context))):
                best = s
        return best

    # ------------------------------------------------------------------ ownership
    def _service_named(self, name: str, near: Path) -> Service | None:
        """Service by bare name; with several compose projects, the one whose compose file is closest to `near` wins."""
        cands = [s for s in self.services.values() if s.name == name]
        if len(cands) <= 1:
            return cands[0] if cands else None
        def depth(s: Service) -> int:
            d = (self.root / s.compose_file).parent
            try:
                return -len(near.resolve().relative_to(d.resolve()).parts)
            except ValueError:
                return -10_000
        return max(cands, key=depth)

    def catalog_and_owners(self) -> None:
        for f in self.files:
            if f.name in ("catalog-info.yaml", "catalog-info.yml"):
                rel = _rel(self.root, f)
                try:
                    docs = list(yaml.safe_load_all(read(f)))
                except yaml.YAMLError:
                    continue
                for d in docs:
                    if not isinstance(d, dict) or d.get("kind") not in ("Component", "System", "API"):
                        continue
                    md, spec = d.get("metadata") or {}, d.get("spec") or {}
                    name = str(md.get("name", ""))
                    svc = self._service_named(name, f)
                    key = svc.key if svc else f"component:catalog/{name}"
                    self.r.node("static", key, "container" if svc else "component", name, V_CATALOG,
                                attrs={"owner": spec.get("owner", ""), "lifecycle": spec.get("lifecycle", ""),
                                       "catalog_type": spec.get("type", ""), "description": md.get("description", "")},
                                ref=rel, span={"path": rel})
            if f.name == "CODEOWNERS":
                rel = _rel(self.root, f)
                for i, line in enumerate(read(f).splitlines(), 1):
                    parts = line.split()
                    if not parts or parts[0].startswith("#") or len(parts) < 2:
                        continue
                    pattern, owners = parts[0], parts[1:]
                    for s in self.services.values():
                        if not s.context:
                            continue
                        crel = "/" + _rel(self.root, s.context).strip("/") + "/"
                        pat = pattern if pattern.startswith("/") else "/" + pattern
                        if pattern == "*" or crel.startswith(pat.rstrip("*")) or fnmatch.fnmatch(crel, pat):
                            self.r.node("static", s.key, "container", s.name, V_CODEOWNERS, attrs={"owner": " ".join(owners)},
                                        ref=rel, span={"path": rel, "line_start": i, "line_end": i})

    # ------------------------------------------------------------------ documents
    def tables(self) -> None:
        """Tables and columns declared in code (SQL, Alembic, SQLAlchemy, Django) -> `table` elements with full column lists."""
        decl = db_schema.extract(self.root, self.files, read)
        for name, t in sorted(decl.items()):
            first = t.sources[0]
            owner = self._owner_service(self.root / first["path"])
            system = owner.system if owner else self.repo
            self.by_system.setdefault(system, {})
            tk = f"table:{system}/code/{name}"
            cols = [{"name": c.name, "type": c.type, "nullable": c.nullable, "primary_key": c.primary_key, "references": c.references}
                    for c in t.columns.values()]
            self.r.node("static", tk, "table", name, db_schema.V_SCHEMA, ref=first["path"],
                        span={"path": first["path"], "line_start": first["line"]},
                        attrs={"columns": cols, "column_count": len(cols), "declared_in": t.sources[:12], "declared_by": sorted({x["kind"] for x in t.sources}),
                               "owner": owner.name if owner else "", "description": f"{len(cols)} columns · declared in {first['path']}"})
            src = owner.key if owner else f"system:{system}"
            self.r.edge("static", src, "references", tk, db_schema.V_SCHEMA, attrs={"relation": "declares schema"}, ref=first["path"],
                        span={"path": first["path"], "line_start": first["line"]})
            for c in t.columns.values():
                if c.references:
                    target = c.references.split(".")[-2] if c.references.count(".") >= 1 else c.references
                    if target in decl and target != name:
                        self.r.edge("static", tk, "references", f"table:{system}/code/{target}", db_schema.V_SCHEMA,
                                    attrs={"relation": "foreign key", "column": c.name, "target_column": c.references}, ref=first["path"])
        if decl:
            self.r.stats["tables"] = len(decl)

    CODE_EXT = {".py": "python", ".ts": "typescript", ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript", ".java": "java",
                ".kt": "kotlin", ".go": "go", ".cs": "csharp", ".rb": "ruby", ".php": "php", ".rs": "rust", ".sql": "sql",
                ".proto": "protobuf", ".graphql": "graphql", ".prisma": "prisma"}
    CODE_PRIORITY = re.compile(r"(model|schema|migration|alembic|entity|entities|repository|repositories|dao|table|sql|route|router|api|"
                               r"controller|handler|endpoint|service|consumer|producer|config|settings|main|app)", re.IGNORECASE)
    MAX_CODE_FILES = 1500

    def code_index(self) -> None:
        """Source files as searchable documents (tag `code`) so the assistant can answer from the code itself.
        Prioritizes models, schemas, migrations, APIs and services; tests, generated and vendored files are skipped."""
        cands = []
        for f in self.files:
            lang = self.CODE_EXT.get(f.suffix.lower())
            if not lang or f.stat().st_size > 150_000 or f.name.endswith((".min.js", ".d.ts", ".pyi")):
                continue
            rel = _rel(self.root, f)
            parts = set(Path(rel).parts)
            if parts & {"tests", "test", "__tests__", "spec", "generated", "vendor", "third_party", "migrations_old"} or ".test." in f.name or f.name.startswith("test_"):
                continue
            score = (0 if self.CODE_PRIORITY.search(rel) else 1, len(Path(rel).parts), rel)
            cands.append((score, f, rel, lang))
        cands.sort(key=lambda x: x[0])
        if len(cands) > self.MAX_CODE_FILES:
            self.r.warnings.append(f"code index limited to {self.MAX_CODE_FILES} of {len(cands)} source files (models, schemas, APIs first)")
        for _, f, rel, lang in cands[: self.MAX_CODE_FILES]:
            text = read(f)
            if not text.strip() or "\x00" in text[:2000]:
                continue
            self.r.documents.append(DocumentOut(path=rel, title=rel, text=text, mime="text/x-code", tags=["code", lang]))
        self.r.stats["code_files_indexed"] = min(len(cands), self.MAX_CODE_FILES)

    def _documented(self, rel: str, blocks: list[tuple[str, str]]) -> None:
        """Relations drawn in architecture diagrams inside the docs: `inferred` (documented intent, not observed),
        between names the builder resolves to real elements across every datasource."""
        n = 0
        for lang, body in blocks:
            for a, rel_kind, b, label in diagram_edges(lang, body):
                self.r.edge("inferred", f"name:{a}", rel_kind, f"name:{b}", V_DIAGRAM, ref=rel, span={"path": rel},
                            attrs={"documented": True, "diagram": rel, "notation": lang, "label": label[:120], "resolved_by": "name"},
                            confidence=0.6)
                n += 1
                if n >= 300:
                    return

    def _wants_doc(self, rel: str, f: Path) -> bool:
        """docs mode: every document anywhere. auto/code: root files, conventional doc folders and ADR folders anywhere."""
        if self.content == "docs":
            return True
        if self.content == "code" and f.parent != self.root and not rel.startswith(DOC_PREFIXES):
            return False
        return f.parent == self.root or rel.startswith(DOC_PREFIXES) or bool(ADR_PATH.search(rel))

    def docs(self) -> None:
        count, limit = 0, 2000 if self.content == "docs" else 400
        binaries: list[str] = []
        for f in self.files:
            suf = f.suffix.lower()
            rel = _rel(self.root, f)
            if suf in BINARY_DOCS and self._wants_doc(rel, f):
                binaries.append(rel)            # parsed by the connector through docling-serve when available
                continue
            is_text = suf in (".md", ".mdx") or (self.content == "docs" and suf in DOC_TEXT)
            is_diagram = suf in DIAGRAM_TEXT and (self.content == "docs" or rel.startswith(DOC_PREFIXES) or bool(ADR_PATH.search(rel)))
            if not (is_text or is_diagram) or f.stat().st_size > 300_000 or not self._wants_doc(rel, f):
                continue
            text = read(f)
            if is_diagram:
                lang = DIAGRAM_TEXT[suf]
                title = f"{f.stem} ({lang} diagram)"[:200]
                text = f"# {title}\n\nSource: `{rel}`\n\n```{lang}\n{text}\n```\n"
                tags = ["diagram", lang]
            else:
                m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
                title = (m.group(1).strip() if m else f.stem)[:200]
                tags = ["adr"] if ADR_PATH.search(rel) or re.match(r"^(adr[-_]?)?\d{3,4}[-_]", f.name, re.IGNORECASE) else []
            mime = "text/markdown" if suf in (".md", ".mdx", ".markdown") or is_diagram else "text/plain"
            self.r.documents.append(DocumentOut(path=rel, title=title, text=text, mime=mime, tags=tags))
            blocks = [(DIAGRAM_TEXT[suf], read(f))] if is_diagram else \
                [(lang if lang != "puml" else "plantuml", body) for lang, body in
                 re.findall(r"```(mermaid|plantuml|puml|structurizr)\s*\n(.*?)```", text, re.DOTALL)]
            self._documented(rel, blocks)
            if "adr" in tags and suf in (".md", ".mdx", ".markdown"):
                ak = f"adr:{self.repo}/{rel}"
                self.r.node("static", ak, "adr", title, V_DOCS, attrs={"path": rel, "imported": True}, ref=rel,
                            span={"path": rel, "line_start": 1})
            count += 1
            if count >= limit:
                self.r.warnings.append(f"document limit ({limit}) reached; remaining documents not ingested")
                break
        if binaries:
            self.r.artifacts.append({"kind": "binary-documents", "paths": binaries[:200]})


def analyze_repository(root: Path, revision: str, repo_name: str, content: str = "auto") -> ScanResult:
    return RepoAnalyzer(root, revision, repo_name, content).run()

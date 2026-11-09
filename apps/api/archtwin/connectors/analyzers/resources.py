"""Resources a code module uses, recognized from its imports and calls (static evidence, per module, with file:line).

A resource is something outside the module's own code that it talks to or runs: a SaaS API, an embedded database, an
object store, a cache, a search engine, a local ML runtime or an external tool. Each kind maps to an element the graph
builder can show and connect: the importing component -> resource edge (and its container rolls the edge up).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

V_RESOURCES = "code-resources/1.0"


@dataclass(frozen=True)
class Resource:
    key: str                # element key; "{system}" is replaced with the owning system
    name: str
    kind: str               # graph node kind
    subtype: str
    relation: str           # calls | reads | writes
    protocol: str
    technology: str


LIBS: dict[str, Resource] = {
    "openai": Resource("external:openai", "OpenAI API", "external-system", "saas", "calls", "https", "OpenAI"),
    "anthropic": Resource("external:anthropic", "Anthropic API", "external-system", "saas", "calls", "https", "Anthropic"),
    "litellm": Resource("external:llm-gateway", "LLM gateway (LiteLLM)", "external-system", "gateway", "calls", "https", "LiteLLM"),
    "sqlite3": Resource("database:{system}/sqlite", "SQLite (embedded)", "database", "database", "writes", "sqlite", "SQLite"),
    "aiosqlite": Resource("database:{system}/sqlite", "SQLite (embedded)", "database", "database", "writes", "sqlite", "SQLite"),
    "boto3": Resource("external:s3", "S3 object storage", "external-system", "storage", "writes", "https", "S3"),
    "minio": Resource("external:s3", "S3 object storage", "external-system", "storage", "writes", "https", "S3 (MinIO)"),
    "redis": Resource("external:redis", "Redis", "external-system", "cache", "writes", "redis", "Redis"),
    "pymongo": Resource("external:mongodb", "MongoDB", "external-system", "database", "writes", "mongodb", "MongoDB"),
    "motor": Resource("external:mongodb", "MongoDB", "external-system", "database", "writes", "mongodb", "MongoDB"),
    "elasticsearch": Resource("external:elasticsearch", "Elasticsearch", "external-system", "database", "reads", "http", "Elasticsearch"),
    "opensearchpy": Resource("external:opensearch", "OpenSearch", "external-system", "database", "reads", "http", "OpenSearch"),
    "neo4j": Resource("external:neo4j", "Neo4j", "external-system", "database", "reads", "bolt", "Neo4j"),
    "qdrant_client": Resource("external:qdrant", "Qdrant", "external-system", "database", "reads", "http", "Qdrant"),
    "smtplib": Resource("external:smtp", "Mail server (SMTP)", "external-system", "saas", "calls", "smtp", "SMTP"),
    "fastembed": Resource("component:{system}/{service}/ml-runtime", "Local ML inference", "component", "ml", "calls", "in-process", "fastembed / ONNX"),
    "onnxruntime": Resource("component:{system}/{service}/ml-runtime", "Local ML inference", "component", "ml", "calls", "in-process", "ONNX Runtime"),
    "torch": Resource("component:{system}/{service}/ml-runtime", "Local ML inference", "component", "ml", "calls", "in-process", "PyTorch"),
    "transformers": Resource("component:{system}/{service}/ml-runtime", "Local ML inference", "component", "ml", "calls", "in-process", "Transformers"),
    "mediapipe": Resource("component:{system}/{service}/ml-runtime", "Local ML inference", "component", "ml", "calls", "in-process", "MediaPipe"),
    "cv2": Resource("component:{system}/{service}/ml-runtime", "Local ML inference", "component", "ml", "calls", "in-process", "OpenCV"),
}
TOOLS = {"ffmpeg": Resource("external:{system}/ffmpeg", "ffmpeg (external tool)", "external-system", "tool", "calls", "process", "ffmpeg"),
         "exiftool": Resource("external:{system}/exiftool", "exiftool (external tool)", "external-system", "tool", "calls", "process", "exiftool")}
TOOL_CALL = re.compile(r"""(?:subprocess\.\w+|Popen|run|check_output|create_subprocess_exec)\s*\(\s*\[?\s*['"](ffmpeg|ffprobe|exiftool)['"]""")


def resources_for(imports: set[str], source: str) -> list[tuple[Resource, str]]:
    """(resource, evidence hint) for one module: top-level imported packages plus external tools started as processes."""
    out: dict[str, tuple[Resource, str]] = {}
    for imp in sorted(imports):
        top = imp.split(".")[0]
        if top in LIBS and LIBS[top].key not in out:
            out[LIBS[top].key] = (LIBS[top], f"import {top}")
    for m in TOOL_CALL.finditer(source):
        tool = "ffmpeg" if m.group(1) in ("ffmpeg", "ffprobe") else m.group(1)
        r = TOOLS[tool]
        out.setdefault(r.key, (r, f"runs {m.group(1)}"))
    return list(out.values())


def import_line(source: str, top: str) -> int:
    m = re.search(rf"^\s*(?:import|from)\s+{re.escape(top)}\b", source, re.MULTILINE)
    return source.count("\n", 0, m.start()) + 1 if m else 1

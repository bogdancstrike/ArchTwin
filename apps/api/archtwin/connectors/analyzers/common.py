"""Shared helpers for static analyzers: safe file walking, classification of images/technologies, URL host extraction."""
from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".cache", "coverage", "test-results",
             ".pytest_cache", ".ruff_cache", ".mypy_cache", ".hypothesis", ".idea", ".vscode", "target", ".next", ".claude",
             "playwright-report", "site-packages", ".tox"}
SECRET_FILE = re.compile(r"(^\.env($|\.)|\.pem$|\.key$|\.p12$|\.pfx$|id_rsa|id_ed25519|\.kdbx$|credentials|secrets?\.(ya?ml|json)$)", re.IGNORECASE)
MAX_FILE = 1_000_000


def walk(root: Path, max_files: int = 20000) -> Iterator[Path]:
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".") or d in (".github",))
        for f in sorted(filenames):
            if SECRET_FILE.search(f):
                continue                                  # secret files are never read
            p = Path(dirpath) / f
            try:
                if p.is_symlink() or p.stat().st_size > MAX_FILE:
                    continue
            except OSError:
                continue
            n += 1
            if n > max_files:
                return
            yield p


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


TECH = [  # (regex on image/name, node subtype, technology label)
    (r"postgres|pgvector|cockroach|timescale", "database", "PostgreSQL"),
    (r"mysql|mariadb", "database", "MySQL"),
    (r"mongo", "database", "MongoDB"),
    (r"clickhouse", "database", "ClickHouse"),
    (r"elasticsearch|opensearch", "database", "Search engine"),
    (r"neo4j|arangodb", "database", "Graph database"),
    (r"qdrant|weaviate|milvus", "database", "Vector database"),
    (r"redis|valkey|memcached|dragonfly", "cache", "Cache"),
    (r"schema-registry|apicurio|karapace", "queue", "Schema registry"),
    (r"kafka|redpanda|rabbitmq|nats|pulsar", "queue", "Message broker"),
    (r"seaweedfs|minio|s3", "storage", "Object storage"),
    (r"keycloak|dex|authentik", "identity", "Identity provider"),
    (r"cerbos|opa|openfga", "policy", "Policy engine"),
    (r"temporal(?!.*ui)", "workflow", "Workflow engine"),
    (r"litellm", "gateway", "AI gateway"),
    (r"langfuse", "observability", "LLM observability"),
    (r"jaeger|tempo|prometheus|grafana|loki|otel", "observability", "Observability"),
    (r"docling", "service", "Document parser"),
    (r"searxng", "service", "Metasearch"),
    (r"clamav", "service", "Antivirus"),
    (r"nginx|caddy|traefik|envoy|haproxy", "webapp", "Web server / proxy"),
    (r"socket-proxy", "service", "Docker API proxy"),
]


def classify(*names: str) -> tuple[str, str]:
    s = " ".join(n for n in names if n).lower()
    for rx, sub, tech in TECH:
        if re.search(rx, s):
            return sub, tech
    return "service", ""


URL_RX = re.compile(r"(?P<scheme>[a-z][a-z0-9+.\-]*)://(?:[^@/\s\"']*@)?(?P<host>[A-Za-z0-9_.\-]+)(?::(?P<port>\d+|\$\{[^}]+\}))?(?P<path>/[^\s\"']*)?")
HOSTPORT_RX = re.compile(r"^(?P<host>[A-Za-z][A-Za-z0-9_.\-]*):(?P<port>\d{2,5})$")

SCHEME_REL = {"postgresql": ("writes", "postgresql"), "postgres": ("writes", "postgresql"), "mysql": ("writes", "mysql"),
              "mongodb": ("writes", "mongodb"), "redis": ("calls", "redis"), "rediss": ("calls", "redis"),
              "amqp": ("publishes", "amqp"), "kafka": ("publishes", "kafka"), "http": ("calls", "http"), "https": ("calls", "https"),
              "grpc": ("calls", "grpc"), "clickhouse": ("writes", "clickhouse"), "jdbc": ("writes", "jdbc"), "nats": ("publishes", "nats")}


def scheme_base(s: str) -> str:
    return s.split("+")[0].lower()


def safe_url(u: str) -> str:
    """Drop credentials from URLs before they become evidence (never store secrets)."""
    return re.sub(r"(?<=://)[^@/\s]*@", "", u)

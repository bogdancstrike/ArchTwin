"""Connector SDK (AT-CONNECTOR_PLATFORM-001): protocol, manifest, observation builder.

Connectors are READ-ONLY (ADR-0006): the SDK has no write methods; manifests declare read scopes only.
Every observation carries origin, source revision, observed_at, parser/mapping version and confidence (evidence first).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, field_validator

Origin = Literal["desired", "static", "runtime", "planned", "issue", "inferred", "manual"]
NODE_KINDS = {"person", "software-system", "external-system", "container", "component", "service", "library", "api-endpoint",
              "api-contract", "event-schema", "kafka-topic", "consumer-group", "database", "db-schema", "table", "deployment",
              "workload", "network-zone", "team", "adr", "work-item", "document"}
EDGE_KINDS = {"contains", "depends-on", "calls", "publishes", "consumes", "reads", "writes", "deploys-as", "hosted-on", "exposes",
              "authenticated-by", "owned-by", "implements", "decided-by", "tracked-by", "derived-from", "integrates-with", "references"}


class Observation(BaseModel):
    """Normalized observation — validated before commit (AT-NORMALIZATION_FRESHNESS-001)."""
    origin: Origin
    subject_kind: Literal["node", "edge"]
    subject_key: str = Field(min_length=3, max_length=600)
    kind: str
    name: str = Field(max_length=400)
    attributes: dict[str, Any] = {}
    source_ref: str = ""
    source_revision: str = ""
    evidence: dict[str, Any] = {}
    parser_version: str
    confidence: float = Field(ge=0, le=1, default=1.0)
    sensitive: bool = False

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str, info):
        allowed = NODE_KINDS if info.data.get("subject_kind") == "node" else EDGE_KINDS
        if v not in allowed:
            raise ValueError(f"unknown {info.data.get('subject_kind')} kind {v!r}")
        return v


def edge_key(src: str, rel: str, dst: str) -> str:
    return f"{src}|{rel}|{dst}"


@dataclass
class DocumentOut:
    path: str
    title: str
    text: str
    mime: str = "text/markdown"
    tags: list[str] = field(default_factory=list)


@dataclass
class ScanResult:
    observations: list[Observation] = field(default_factory=list)
    documents: list[DocumentOut] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    revision: str = ""
    complete: bool = True
    coverage: dict[str, Any] = field(default_factory=dict)       # {"origin":..., "prefixes":[...], "systems":[...]}
    stats: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def node(self, origin: Origin, key: str, kind: str, name: str, parser: str, *, attrs: dict | None = None, ref: str = "",
             span: dict | None = None, confidence: float = 1.0, sensitive: bool = False) -> str:
        self.observations.append(Observation(origin=origin, subject_kind="node", subject_key=key, kind=kind, name=name[:400],
                                             attributes=attrs or {}, source_ref=ref, source_revision=self.revision,
                                             evidence=span or {}, parser_version=parser, confidence=confidence, sensitive=sensitive))
        return key

    def edge(self, origin: Origin, src: str, rel: str, dst: str, parser: str, *, attrs: dict | None = None, ref: str = "",
             span: dict | None = None, confidence: float = 1.0, name: str = "") -> str:
        k = edge_key(src, rel, dst)
        self.observations.append(Observation(origin=origin, subject_kind="edge", subject_key=k, kind=rel, name=name or rel,
                                             attributes={"source": src, "target": dst, **(attrs or {})}, source_ref=ref,
                                             source_revision=self.revision, evidence=span or {}, parser_version=parser,
                                             confidence=confidence))
        return k


@dataclass
class TestResult:
    ok: bool
    scopes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class Connector(Protocol):
    kind: str
    flag: str
    manifest: dict[str, Any]

    async def test(self, config: dict[str, Any], secret: dict[str, Any]) -> TestResult: ...
    async def scan(self, config: dict[str, Any], secret: dict[str, Any], ref: str | None) -> ScanResult: ...


def now() -> datetime:
    return datetime.now(UTC)

"""Request DTOs (independent from storage). Unknown fields are rejected; client-supplied org_id is never accepted."""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="ignore")      # ignored, not trusted (e.g. a smuggled org_id is dropped)


class ProjectIn(Strict):
    title: str = Field(min_length=2, max_length=120)
    purpose: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    environments: list[str] = Field(default_factory=lambda: ["production"], max_length=10)


class ProjectPatch(Strict):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    purpose: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None
    status: Literal["active", "archived"] | None = None


class MemberIn(Strict):
    user_id: uuid.UUID
    role: str | None


class FlagIn(Strict):
    scope_kind: Literal["org", "project"]
    scope_id: str | None = None
    value: bool
    enforce: bool = False
    reason: str = Field(default="", max_length=500)


class ConnectorIn(Strict):
    kind: str
    name: str = Field(min_length=2, max_length=80)
    config: dict[str, Any] = Field(default_factory=dict)
    secret: dict[str, Any] | None = None
    freshness_sla_s: int | None = Field(default=None, ge=60, le=30 * 86400)


class ScanIn(Strict):
    ref: str | None = Field(default=None, max_length=200)


class BaselineIn(Strict):
    snapshot_id: uuid.UUID
    note: str = Field(default="", max_length=2000)


class DecisionIn(Strict):
    note: str = Field(default="", max_length=2000)


class ManualElementIn(Strict):
    subject_kind: Literal["node", "edge"]
    key: str = Field(min_length=3, max_length=600)
    kind: str
    name: str = Field(min_length=1, max_length=200)
    attributes: dict[str, Any] = Field(default_factory=dict)
    retract: bool = False


class MergeIn(Strict):
    alias_key: str
    canonical_key: str
    reason: str = Field(default="", max_length=500)


class LayoutIn(Strict):
    overrides: dict[str, dict[str, float]]
    revision: int | None = None


class AdrIn(Strict):
    title: str = Field(min_length=3, max_length=300)
    context: str = ""
    decision_drivers: list[str] = Field(default_factory=list)
    considered_options: list[dict[str, Any]] = Field(default_factory=list)
    decision_outcome: str = ""
    consequences: str = ""
    links: list[str] = Field(default_factory=list)


class AdrDecideIn(Strict):
    supersedes: uuid.UUID | None = None


class TransitionIn(Strict):
    status: str
    note: str = Field(default="", max_length=4000)
    suppress_days: int | None = Field(default=None, ge=1, le=365)
    assignee: uuid.UUID | None = None


class CommentIn(Strict):
    body: str = Field(min_length=1, max_length=4000)


class AskIn(Strict):
    question: str = Field(min_length=3, max_length=4000)
    model: str | None = None
    mode: Literal["ask", "design"] = "ask"
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)
    scope: Literal["data", "general"] = "data"          # data = grounded in project evidence; general = no project data
    sources: list[str] | None = Field(default=None, max_length=50)   # data scope: connector ids, "uploads", "adrs"; None = all
    conversation_id: uuid.UUID | None = None


class GenerateIn(Strict):
    template: Literal["system-overview", "container-catalog", "interface-catalog"]


class ManualDocIn(Strict):
    content: str = Field(max_length=500_000)


class TokensIn(Strict):
    tokens: dict[str, str]


class PrefsIn(Strict):
    preferred_model: str | None = None
    theme: Literal["light", "dark", "system"] | None = None


class SpendLimitItem(Strict):
    subject: str = Field(min_length=6, max_length=60)          # global | user:<uuid> | project:<uuid>
    monthly_usd: float | None = Field(default=None, ge=0, le=1_000_000)


class SpendLimitsIn(Strict):
    items: list[SpendLimitItem] = Field(max_length=200)


class SourceRootsIn(Strict):
    roots: list[str] | None = Field(default=None, max_length=50)   # None = every mounted boundary


class ExtendIn(Strict):
    text: str = Field(min_length=1, max_length=12000)
    mode: Literal["extend", "improve", "concise"] = "extend"
    field: str = Field(default="", max_length=60)
    title: str = Field(default="", max_length=300)
    instruction: str = Field(default="", max_length=1000)
    grounded: bool = True
    model: str | None = None

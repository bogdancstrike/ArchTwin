"""All tables (SQLAlchemy Core). Each block is owned by one module; other modules go through that module's service.

Tenant tables carry org_id (+ project_id). RLS policies are created in the Alembic migration.
"""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID

from archtwin.common.db import metadata


def ts(name="created_at", nullable=False, default=True):
    return Column(name, DateTime(timezone=True), nullable=nullable, server_default=func.now() if default else None)

def uid(name, nullable=False, **kw):
    return Column(name, UUID(as_uuid=True), nullable=nullable, **kw)

def scoped():          # org + project columns with composite FK to projects (no cross-project ambiguity)
    return [uid("org_id"), uid("project_id")]

def proj_fk():
    return ForeignKeyConstraint(["org_id", "project_id"], ["projects.org_id", "projects.id"], ondelete="CASCADE")

J = lambda name, default="'{}'::jsonb": Column(name, JSONB, nullable=False, server_default=text(default))

# ------------------------------------------------------------------ iam (non-tenant identity + org membership)
users = Table("users", metadata,
    uid("id", primary_key=True), Column("subject", Text, nullable=False, unique=True), Column("username", Text, nullable=False),
    Column("email", Text), Column("display_name", Text, nullable=False), Column("realm_roles", ARRAY(Text), nullable=False, server_default="{}"),
    J("preferences"), ts(), ts("last_seen_at"))

organizations = Table("organizations", metadata,
    uid("id", primary_key=True), Column("name", Text, nullable=False), Column("slug", Text, nullable=False, unique=True),
    J("settings"), ts())

org_members = Table("org_members", metadata,
    uid("org_id"), uid("user_id"), Column("role", Text, nullable=False), ts(),
    PrimaryKeyConstraint("org_id", "user_id"),
    ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"))

# ------------------------------------------------------------------ projects (RLS: org)
projects = Table("projects", metadata,
    uid("id", primary_key=True), uid("org_id"), Column("slug", Text, nullable=False), Column("title", Text, nullable=False),
    Column("purpose", Text, nullable=False, server_default=""), Column("tags", ARRAY(Text), nullable=False, server_default="{}"),
    Column("status", Text, nullable=False, server_default="active"), uid("created_by"), ts(), ts("updated_at"),
    Column("revision", Integer, nullable=False, server_default="1"),
    ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    UniqueConstraint("org_id", "slug"), UniqueConstraint("org_id", "id", name="uq_projects_org_id_id"))

environments = Table("environments", metadata,
    uid("id", primary_key=True), *scoped(), Column("name", Text, nullable=False),
    Column("criticality", Text, nullable=False, server_default="normal"), ts(), proj_fk(), UniqueConstraint("project_id", "name"))

project_members = Table("project_members", metadata,
    *scoped(), uid("user_id"), Column("role", Text, nullable=False), ts(),
    PrimaryKeyConstraint("project_id", "user_id"), proj_fk(),
    ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"))

# ------------------------------------------------------------------ flags (non-tenant table, explicit scope columns)
flag_overrides = Table("flag_overrides", metadata,
    uid("id", primary_key=True), Column("flag_key", Text, nullable=False), Column("scope_kind", Text, nullable=False),
    Column("scope_id", Text, nullable=False, server_default=""), Column("value", Boolean, nullable=False),
    Column("enforce", Boolean, nullable=False, server_default="false"), Column("reason", Text, nullable=False, server_default=""),
    uid("updated_by", nullable=True), ts("updated_at"), UniqueConstraint("flag_key", "scope_kind", "scope_id"))

# ------------------------------------------------------------------ audit (RLS: org; append-only, hash chained)
audit_events = Table("audit_events", metadata,
    uid("id", primary_key=True), uid("org_id"), Column("seq", BigInteger, nullable=False), ts("occurred_at"),
    uid("actor_id", nullable=True), Column("actor_name", Text, nullable=False), Column("action", Text, nullable=False),
    Column("resource_kind", Text, nullable=False), Column("resource_id", Text, nullable=False, server_default=""),
    uid("project_id", nullable=True), Column("decision", Text, nullable=False), Column("trace_id", Text, nullable=False, server_default=""),
    J("details"), Column("prev_hash", Text, nullable=False), Column("hash", Text, nullable=False),
    UniqueConstraint("org_id", "seq"), Index("ix_audit_org_time", "org_id", "occurred_at"))

audit_chain_heads = Table("audit_chain_heads", metadata,
    uid("org_id", primary_key=True), Column("seq", BigInteger, nullable=False), Column("hash", Text, nullable=False))

# ------------------------------------------------------------------ kernel (outbox, idempotency)
outbox_events = Table("outbox_events", metadata,
    uid("id", primary_key=True), uid("org_id"), uid("project_id", nullable=True), Column("aggregate_kind", Text, nullable=False),
    Column("aggregate_id", Text, nullable=False), Column("event_kind", Text, nullable=False), J("payload"), ts("occurred_at"),
    Column("status", Text, nullable=False, server_default="pending"), Column("attempts", Integer, nullable=False, server_default="0"),
    ts("next_attempt_at"), Column("last_error", Text), Column("delivered_at", DateTime(timezone=True)),
    Index("ix_outbox_pending", "status", "next_attempt_at"))

consumer_receipts = Table("consumer_receipts", metadata,
    Column("consumer", Text, nullable=False), uid("event_id"), ts("processed_at"), PrimaryKeyConstraint("consumer", "event_id"))

idempotency_keys = Table("idempotency_keys", metadata,
    uid("user_id"), Column("key", Text, nullable=False), Column("method", Text, nullable=False), Column("path", Text, nullable=False),
    Column("request_hash", Text, nullable=False), Column("status_code", Integer, nullable=False), J("response", "'null'::jsonb"), ts(),
    PrimaryKeyConstraint("user_id", "key"))

# ------------------------------------------------------------------ connectors (RLS: org + project)
secrets = Table("secrets", metadata,
    uid("id", primary_key=True), *scoped(), Column("kek_id", Text, nullable=False), Column("wrapped_dek", LargeBinary, nullable=False),
    Column("dek_nonce", LargeBinary, nullable=False), Column("nonce", LargeBinary, nullable=False),
    Column("ciphertext", LargeBinary, nullable=False), ts(), proj_fk())

connectors = Table("connectors", metadata,
    uid("id", primary_key=True), *scoped(), Column("kind", Text, nullable=False), Column("name", Text, nullable=False),
    J("config"), uid("secret_id", nullable=True), Column("freshness_sla_s", Integer, nullable=False, server_default="86400"),
    Column("enabled", Boolean, nullable=False, server_default="true"), uid("created_by", nullable=True), ts(),
    uid("last_scan_id", nullable=True), Column("last_success_at", DateTime(timezone=True)),
    Column("last_complete_at", DateTime(timezone=True)), Column("last_status", Text, nullable=False, server_default="never"),
    proj_fk(), UniqueConstraint("project_id", "name"))

scan_runs = Table("scan_runs", metadata,
    uid("id", primary_key=True), *scoped(), uid("connector_id"), Column("status", Text, nullable=False, server_default="queued"),
    Column("mode", Text, nullable=False, server_default="full"), Column("ref", Text), Column("revision", Text),
    uid("requested_by", nullable=True), ts(), Column("started_at", DateTime(timezone=True)), Column("finished_at", DateTime(timezone=True)),
    J("stats"), J("coverage"), Column("error", Text), proj_fk(), Index("ix_scan_runs_connector", "connector_id", "created_at"))

# ------------------------------------------------------------------ inventory (RLS; observations append-only)
source_artifacts = Table("source_artifacts", metadata,
    uid("id", primary_key=True), *scoped(), uid("connector_id"), uid("scan_id"), Column("uri", Text, nullable=False),
    Column("sha256", Text, nullable=False), Column("kind", Text, nullable=False), Column("revision", Text),
    Column("size", BigInteger, nullable=False, server_default="0"), Column("parser_version", Text, nullable=False),
    ts("observed_at"), proj_fk())

observations = Table("observations", metadata,
    uid("id", primary_key=True), *scoped(), uid("connector_id", nullable=True), uid("scan_id", nullable=True),
    Column("origin", Text, nullable=False), Column("subject_kind", Text, nullable=False), Column("subject_key", Text, nullable=False),
    Column("kind", Text, nullable=False), Column("name", Text, nullable=False), J("attributes"),
    Column("source_ref", Text, nullable=False, server_default=""), Column("source_revision", Text, nullable=False, server_default=""),
    J("evidence"), ts("observed_at"), Column("parser_version", Text, nullable=False),
    Column("confidence", Numeric(4, 3), nullable=False, server_default="1"), Column("sensitive", Boolean, nullable=False, server_default="false"),
    uid("created_by", nullable=True), proj_fk(),
    Index("ix_obs_scan", "project_id", "scan_id"), Index("ix_obs_subject", "project_id", "subject_key"))

identity_aliases = Table("identity_aliases", metadata,
    uid("id", primary_key=True), *scoped(), Column("alias_key", Text, nullable=False), Column("canonical_key", Text, nullable=False),
    Column("reason", Text, nullable=False, server_default=""), uid("created_by", nullable=True), ts(), proj_fk(),
    UniqueConstraint("project_id", "alias_key"))

identity_suggestions = Table("identity_suggestions", metadata,
    uid("id", primary_key=True), *scoped(), Column("key_a", Text, nullable=False), Column("key_b", Text, nullable=False),
    Column("score", Numeric(4, 3), nullable=False), Column("reason", Text, nullable=False, server_default=""),
    Column("status", Text, nullable=False, server_default="open"), ts(), proj_fk(), UniqueConstraint("project_id", "key_a", "key_b"))

# ------------------------------------------------------------------ architecture (RLS; snapshots immutable)
snapshots = Table("snapshots", metadata,
    uid("id", primary_key=True), *scoped(), Column("version", Integer, nullable=False), Column("manifest_hash", Text, nullable=False),
    Column("node_count", Integer, nullable=False), Column("edge_count", Integer, nullable=False), J("inputs"),
    Column("builder_version", Text, nullable=False), Column("trigger", Text, nullable=False, server_default="scan"),
    ts(), proj_fk(), UniqueConstraint("project_id", "version"))

snapshot_elements = Table("snapshot_elements", metadata,
    uid("snapshot_id"), *scoped(), Column("element_kind", Text, nullable=False), Column("key", Text, nullable=False),
    Column("data", JSONB, nullable=False), PrimaryKeyConstraint("snapshot_id", "element_kind", "key"), proj_fk(),
    ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"], ondelete="CASCADE"))

baselines = Table("baselines", metadata,
    uid("id", primary_key=True), *scoped(), uid("snapshot_id"), Column("status", Text, nullable=False, server_default="proposed"),
    uid("author_id"), uid("approver_id", nullable=True), Column("note", Text, nullable=False, server_default=""),
    ts("proposed_at"), Column("decided_at", DateTime(timezone=True)), proj_fk(),
    ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"]))

# ------------------------------------------------------------------ diagrams
diagram_layouts = Table("diagram_layouts", metadata,
    uid("id", primary_key=True), *scoped(), Column("view_key", Text, nullable=False), J("overrides"),
    Column("revision", Integer, nullable=False, server_default="1"), uid("updated_by", nullable=True), ts("updated_at"),
    proj_fk(), UniqueConstraint("project_id", "view_key"))

# ------------------------------------------------------------------ decisions (ADR, MADR)
adrs = Table("adrs", metadata,
    uid("id", primary_key=True), *scoped(), Column("number", Integer, nullable=False), Column("title", Text, nullable=False),
    Column("status", Text, nullable=False, server_default="proposed"), uid("author_id"), uid("approver_id", nullable=True),
    Column("current_version", Integer, nullable=False, server_default="1"), uid("supersedes_id", nullable=True),
    uid("superseded_by_id", nullable=True), Column("ai_drafted", Boolean, nullable=False, server_default="false"),
    ts(), Column("decided_at", DateTime(timezone=True)), proj_fk(), UniqueConstraint("project_id", "number"))

adr_versions = Table("adr_versions", metadata,
    uid("adr_id"), Column("version", Integer, nullable=False), *scoped(), J("content"), J("links", "'[]'::jsonb"),
    uid("created_by"), ts(), PrimaryKeyConstraint("adr_id", "version"), proj_fk(),
    ForeignKeyConstraint(["adr_id"], ["adrs.id"], ondelete="CASCADE"))

# ------------------------------------------------------------------ documents
documents = Table("documents", metadata,
    uid("id", primary_key=True), *scoped(), Column("title", Text, nullable=False), Column("source_kind", Text, nullable=False),
    uid("connector_id", nullable=True), Column("path", Text, nullable=False, server_default=""), Column("mime", Text, nullable=False),
    Column("sha256", Text, nullable=False), Column("version", Integer, nullable=False, server_default="1"),
    Column("revision", Text, nullable=False, server_default=""), Column("status", Text, nullable=False, server_default="parsed"),
    Column("parser_version", Text, nullable=False, server_default=""), uid("created_by", nullable=True), ts(), proj_fk(),
    Index("ix_documents_path", "project_id", "path"))

passages = Table("passages", metadata,
    uid("id", primary_key=True), *scoped(), uid("document_id"), Column("ord", Integer, nullable=False), Column("text", Text, nullable=False),
    Column("heading", Text, nullable=False, server_default=""), Column("page", Integer), Column("line_start", Integer),
    Column("line_end", Integer), Column("tsv", TSVECTOR), proj_fk(),
    ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"), Index("ix_passages_tsv", "tsv", postgresql_using="gin"))

generated_docs = Table("generated_docs", metadata,
    uid("id", primary_key=True), *scoped(), Column("template", Text, nullable=False), Column("version", Integer, nullable=False),
    uid("snapshot_id"), Column("content", Text, nullable=False), J("evidence", "'[]'::jsonb"), J("coverage"),
    uid("created_by", nullable=True), ts(), proj_fk(), UniqueConstraint("project_id", "template", "version"))

# ------------------------------------------------------------------ drift
drift_findings = Table("drift_findings", metadata,
    uid("id", primary_key=True), *scoped(), Column("rule_id", Text, nullable=False), Column("rule_version", Text, nullable=False),
    Column("subject_key", Text, nullable=False), Column("title", Text, nullable=False), Column("severity", Text, nullable=False),
    Column("verdict", Text, nullable=False), Column("status", Text, nullable=False, server_default="new"),
    J("expected", "'null'::jsonb"), J("actual", "'null'::jsonb"), J("evidence", "'[]'::jsonb"),
    uid("baseline_id", nullable=True), uid("snapshot_id"), ts("first_seen"), ts("last_seen"),
    Column("occurrences", Integer, nullable=False, server_default="1"), uid("assignee_id", nullable=True),
    Column("suppressed_until", DateTime(timezone=True)), Column("resolution_note", Text, nullable=False, server_default=""),
    ts("updated_at"), proj_fk(), Index("ix_drift_project_status", "project_id", "status"))

drift_comments = Table("drift_comments", metadata,
    uid("id", primary_key=True), *scoped(), uid("finding_id"), uid("author_id"), Column("body", Text, nullable=False), ts(),
    proj_fk(), ForeignKeyConstraint(["finding_id"], ["drift_findings.id"], ondelete="CASCADE"))

drift_evaluations = Table("drift_evaluations", metadata,
    uid("id", primary_key=True), *scoped(), uid("baseline_id", nullable=True), uid("snapshot_id"), J("rule_versions"), J("counts"),
    ts(), proj_fk())

# ------------------------------------------------------------------ notifications (RLS: org)
notifications = Table("notifications", metadata,
    uid("id", primary_key=True), uid("org_id"), uid("project_id", nullable=True), uid("user_id"), Column("kind", Text, nullable=False),
    Column("title", Text, nullable=False), Column("body", Text, nullable=False, server_default=""), Column("link", Text, nullable=False, server_default=""),
    Column("dedupe_key", Text, nullable=False), Column("occurrences", Integer, nullable=False, server_default="1"), ts(),
    Column("read_at", DateTime(timezone=True)), UniqueConstraint("user_id", "dedupe_key"),
    ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"))

# ------------------------------------------------------------------ intelligence
prompt_runs = Table("prompt_runs", metadata,
    uid("id", primary_key=True), *scoped(), uid("user_id"), Column("operation", Text, nullable=False), Column("model", Text, nullable=False),
    Column("question", Text, nullable=False), Column("answer", Text, nullable=False, server_default=""), J("citations", "'[]'::jsonb"),
    J("context_refs", "'[]'::jsonb"), Column("grounded", Boolean, nullable=False, server_default="false"),
    Column("tokens_in", Integer, nullable=False, server_default="0"), Column("tokens_out", Integer, nullable=False, server_default="0"),
    Column("latency_ms", Integer, nullable=False, server_default="0"), Column("trace_id", Text, nullable=False, server_default=""),
    Column("status", Text, nullable=False, server_default="ok"), ts(), proj_fk())

# ------------------------------------------------------------------ webhook ingress (RLS; dedupe of provider deliveries)
webhook_deliveries = Table("webhook_deliveries", metadata,
    uid("id", primary_key=True), *scoped(), uid("connector_id"), Column("delivery_id", Text, nullable=False),
    Column("event", Text, nullable=False), Column("outcome", Text, nullable=False), uid("scan_id", nullable=True),
    J("summary"), ts("received_at"), proj_fk(), UniqueConstraint("connector_id", "delivery_id"),
    Index("ix_webhook_deliveries_time", "project_id", "received_at"))

ORG_RLS = ["projects", "environments", "project_members", "audit_events", "notifications"]
PROJECT_RLS = ["secrets", "connectors", "scan_runs", "source_artifacts", "observations", "identity_aliases",
               "identity_suggestions", "snapshots", "snapshot_elements", "baselines", "diagram_layouts", "adrs",
               "adr_versions", "documents", "passages", "generated_docs", "drift_findings", "drift_comments",
               "drift_evaluations", "prompt_runs", "webhook_deliveries"]
APPEND_ONLY = ["audit_events", "observations", "snapshot_elements", "adr_versions", "source_artifacts"]

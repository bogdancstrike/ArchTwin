"""Assistant conversations (General / Data scopes, saved history), LLM usage ledger + spend limits, architecture AI drafts.

Expand-only (N-1 compatible): new tables + nullable columns on prompt_runs; old code ignores them.

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _rls(table: str) -> None:
    for stmt in (f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
                 f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
                 (f"CREATE POLICY {table}_tenant ON {table} USING (org_id = app_org() AND project_id = app_project()) "
                  "WITH CHECK (org_id = app_org() AND project_id = app_project())"),
                 f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO archtwin_app"):
        op.execute(stmt)


def _org_rls(table: str) -> None:
    for stmt in (f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
                 f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
                 f"CREATE POLICY {table}_tenant ON {table} USING (org_id = app_org()) WITH CHECK (org_id = app_org())",
                 f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO archtwin_app"):
        op.execute(stmt)


def upgrade() -> None:
    uid = postgresql.UUID(as_uuid=True)
    # ---- LLM usage ledger: one row per model call (success or error); the single source of truth for spend
    op.create_table(
        "llm_calls",
        sa.Column("id", uid, primary_key=True),
        sa.Column("org_id", uid, nullable=False),
        sa.Column("project_id", uid, nullable=True),
        sa.Column("user_id", uid, nullable=True),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("cost_source", sa.Text(), nullable=False, server_default="table"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="ok"),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_llm_calls_time", "llm_calls", ["org_id", "created_at"])
    op.create_index("ix_llm_calls_user", "llm_calls", ["user_id", "created_at"])
    op.create_index("ix_llm_calls_project", "llm_calls", ["project_id", "created_at"])
    _org_rls("llm_calls")
    op.execute("CREATE TRIGGER llm_calls_append_only BEFORE UPDATE OR DELETE ON llm_calls FOR EACH ROW EXECUTE FUNCTION archtwin_append_only()")
    # ---- monthly spend limits per subject: global | user:<id> | project:<id>
    op.create_table(
        "spend_limits",
        sa.Column("org_id", uid, nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("monthly_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("updated_by", uid, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("org_id", "subject"),
        sa.CheckConstraint("monthly_usd >= 0", name="ck_spend_limits_nonneg"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    _org_rls("spend_limits")
    # ---- org settings edited by admins in the System page (e.g. the whitelist of local source roots)
    op.create_table(
        "org_settings",
        sa.Column("org_id", uid, nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", uid, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("org_id", "key"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    _org_rls("org_settings")
    op.create_table(
        "conversations",
        sa.Column("id", uid, primary_key=True),
        sa.Column("org_id", uid, nullable=False),
        sa.Column("project_id", uid, nullable=False),
        sa.Column("user_id", uid, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("sources", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("scope IN ('general', 'data')", name="ck_conversations_scope"),
        sa.ForeignKeyConstraint(["org_id", "project_id"], ["projects.org_id", "projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conversations_owner", "conversations", ["project_id", "user_id", "updated_at"])
    _rls("conversations")
    op.add_column("prompt_runs", sa.Column("conversation_id", uid, nullable=True))
    op.add_column("prompt_runs", sa.Column("scope", sa.Text(), nullable=True))
    op.add_column("prompt_runs", sa.Column("evidence", postgresql.JSONB(), nullable=True))
    op.create_index("ix_prompt_runs_conversation", "prompt_runs", ["conversation_id", "created_at"])

    op.create_table(
        "architecture_drafts",
        sa.Column("id", uid, primary_key=True),
        sa.Column("org_id", uid, nullable=False),
        sa.Column("project_id", uid, nullable=False),
        sa.Column("created_by", uid, nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="proposed"),
        sa.Column("content", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("decided_by", uid, nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('proposed', 'accepted', 'partially_accepted', 'rejected')", name="ck_architecture_drafts_status"),
        sa.ForeignKeyConstraint(["org_id", "project_id"], ["projects.org_id", "projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_architecture_drafts_project", "architecture_drafts", ["project_id", "created_at"])
    _rls("architecture_drafts")


def downgrade() -> None:
    op.drop_table("org_settings")
    op.drop_table("spend_limits")
    op.drop_table("llm_calls")
    op.drop_table("architecture_drafts")
    op.drop_index("ix_prompt_runs_conversation", table_name="prompt_runs")
    for c in ("evidence", "scope", "conversation_id"):
        op.drop_column("prompt_runs", c)
    op.drop_table("conversations")

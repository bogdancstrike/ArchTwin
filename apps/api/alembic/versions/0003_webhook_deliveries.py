"""Webhook ingress: delivery dedupe table (project RLS) — phase-02 task 1.5.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connector_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_id", sa.Text(), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id", "project_id"], ["projects.org_id", "projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("connector_id", "delivery_id"),
    )
    op.create_index("ix_webhook_deliveries_time", "webhook_deliveries", ["project_id", "received_at"])
    for stmt in ("ALTER TABLE webhook_deliveries ENABLE ROW LEVEL SECURITY",
                 "ALTER TABLE webhook_deliveries FORCE ROW LEVEL SECURITY",
                 ("CREATE POLICY webhook_deliveries_tenant ON webhook_deliveries USING (org_id = app_org() AND project_id = app_project()) "
                  "WITH CHECK (org_id = app_org() AND project_id = app_project())"),
                 "GRANT SELECT, INSERT, UPDATE, DELETE ON webhook_deliveries TO archtwin_app"):
        op.execute(stmt)


def downgrade() -> None:
    op.drop_table("webhook_deliveries")

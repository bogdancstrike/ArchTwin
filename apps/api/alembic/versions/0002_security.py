"""Row-level security, append-only/immutability triggers, app-role grants, passage FTS.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

# Frozen at the time of this revision (migrations are immutable; later tables get their RLS in their own revision).
ORG_RLS = ["projects", "environments", "project_members", "audit_events", "notifications"]
PROJECT_RLS = ["secrets", "connectors", "scan_runs", "source_artifacts", "observations", "identity_aliases",
               "identity_suggestions", "snapshots", "snapshot_elements", "baselines", "diagram_layouts", "adrs",
               "adr_versions", "documents", "passages", "generated_docs", "drift_findings", "drift_comments",
               "drift_evaluations", "prompt_runs"]
APPEND_ONLY = ["audit_events", "observations", "snapshot_elements", "adr_versions", "source_artifacts"]

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

APP_ROLE = "archtwin_app"


def run(*stmts: str) -> None:
    for s in stmts:
        for part in s.split(";;"):
            if part.strip():
                op.execute(part)


def upgrade() -> None:
    run("""
    CREATE OR REPLACE FUNCTION app_org() RETURNS uuid LANGUAGE sql STABLE AS
      $$ SELECT nullif(current_setting('app.org_id', true), '')::uuid $$;;
    CREATE OR REPLACE FUNCTION app_project() RETURNS uuid LANGUAGE sql STABLE AS
      $$ SELECT nullif(current_setting('app.project_id', true), '')::uuid $$;;

    -- append-only tables: UPDATE never, DELETE only during an explicit purge (project deletion / retention job)
    CREATE OR REPLACE FUNCTION archtwin_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' AND current_setting('app.purge', true) = 'on' AND TG_TABLE_NAME <> 'audit_events' THEN
        RETURN OLD;
      END IF;
      RAISE EXCEPTION 'table % is append-only (% rejected)', TG_TABLE_NAME, TG_OP USING ERRCODE = 'insufficient_privilege';
    END $$;;

    CREATE OR REPLACE FUNCTION archtwin_passage_tsv() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      NEW.tsv := setweight(to_tsvector('english', coalesce(NEW.heading, '')), 'A') || to_tsvector('english', coalesce(NEW.text, ''));
      RETURN NEW;
    END $$;;
    CREATE TRIGGER passages_tsv BEFORE INSERT OR UPDATE ON passages FOR EACH ROW EXECUTE FUNCTION archtwin_passage_tsv();
    """)
    for t in APPEND_ONLY:
        op.execute(f"CREATE TRIGGER {t}_append_only BEFORE UPDATE OR DELETE ON {t} "
                   f"FOR EACH ROW EXECUTE FUNCTION archtwin_append_only()")
    for t in ORG_RLS:
        run(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;; ALTER TABLE {t} FORCE ROW LEVEL SECURITY;;"
                   f"CREATE POLICY {t}_tenant ON {t} USING (org_id = app_org()) WITH CHECK (org_id = app_org());")
    for t in PROJECT_RLS:
        run(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;; ALTER TABLE {t} FORCE ROW LEVEL SECURITY;;"
                   f"CREATE POLICY {t}_tenant ON {t} USING (org_id = app_org() AND project_id = app_project()) "
                   f"WITH CHECK (org_id = app_org() AND project_id = app_project());")
    # app role: DML only, no DDL, never UPDATE/DELETE on audit (belt and braces with the trigger)
    run(f"""
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};;
    REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM {APP_ROLE};;
    REVOKE ALL ON alembic_version FROM {APP_ROLE};;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};
    """)


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}")
    for t in ORG_RLS + PROJECT_RLS:
        run(f"DROP POLICY IF EXISTS {t}_tenant ON {t};; ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;; "
            f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY")
    for t in APPEND_ONLY:
        op.execute(f"DROP TRIGGER IF EXISTS {t}_append_only ON {t}")
    run("DROP TRIGGER IF EXISTS passages_tsv ON passages;; DROP FUNCTION IF EXISTS archtwin_passage_tsv();;"
        "DROP FUNCTION IF EXISTS archtwin_append_only();; DROP FUNCTION IF EXISTS app_project();; DROP FUNCTION IF EXISTS app_org()")

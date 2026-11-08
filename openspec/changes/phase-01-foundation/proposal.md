# Proposal: Secure multi-project foundations

## Why
Every later capability (connectors, graph, drift, AI) handles sensitive architecture data across independent projects. If tenancy, authorization, audit and eventing are retrofitted later, every module must be rewritten and cross-project leaks become likely. This change builds the smallest secure platform that all later phases plug into, and proves it with a **walking skeleton**: one command starts the stack, a user logs in, creates a project, toggles a flag and sees the audit trail.

Users affected: organization admins, project owners, architects (all later personas inherit these guarantees).

## What Changes
- Add **Organizations and governance** (`organizations`).
- Add **Projects and bounded architecture scope** (`project-boundaries`).
- Add **Identity, Cerbos authorization and secrets** (`identity-policy`).
- Add **Feature flags and kill switches** (`feature-flags`).
- Add **Auditability and evidence provenance** (`audit-provenance`).
- Add **Persistent data model and domain events** (`canonical-events`).
- Add **Architect-first UX and workspaces** (`ui-workspaces`).
- Add **LiteLLM, Langfuse and AI provider abstraction** (`llm-gateway`) — infrastructure and smoke test only; no user-facing AI until phase 06.

## Impact
- **Modules:** `kernel` (RequestContext, IDs, errors, outbox), `orgs`, `projects`, `iam`, `flags`, `audit`, `secrets`, `llm_gateway`, web shell.
- **Tables:** organizations, projects, environments, memberships, role_bindings, flag_overrides, flag_revisions, audit_events (hash-chained, append-only), outbox_events, secrets (envelope-encrypted).
- **APIs:** `/api/v1/orgs`, `/projects`, `/projects/{id}/environments`, `/projects/{id}/members`, `/flags`, `/audit`, `/health`, `/admin/diagnostics/llm`.
- **Infrastructure (Docker Compose):** postgres (pgvector image), keycloak, cerbos, temporal (+ UI), valkey, seaweedfs, litellm, langfuse (+ clickhouse), api, worker, web.
- **Adopted OSS:** Keycloak, Cerbos + `cerbos` Python SDK + query-plan SQLAlchemy adapter, OpenFeature Python SDK, Temporal, Alembic, LiteLLM, Langfuse, react-oidc-context. Building any of these in-house is out of scope.
- **Flags introduced:** `module.llm-gateway`, `security.emergency_kill_switch`, and the immutable `security.*` invariants. Core foundation modules are **not** flaggable.

## Dependencies
None — first implementable increment.

## Security risks
Cross-tenant IDOR, stale tenant context on pooled DB connections, policy adapter dropping a filter, secrets in logs, audit tampering. Each has a named control and test in `design.md`.

## Rollout and rollback
- Optional modules default OFF; security invariants are always ON and cannot be flagged.
- All migrations follow expand → migrate → contract; every migration has a tested downgrade or a documented forward-fix.
- Rollback = redeploy previous image + flags; data written by the new version must remain readable by the previous version for one release.
- No external infrastructure mutation occurs in this change.

## Success
- `make up` on a clean machine starts the stack; demo users log in through Keycloak.
- Project A/B isolation suite passes (API, list endpoints, background jobs, caches).
- Every requirement scenario in `specs/` has an automated test; audit chain verifier passes and detects tampering.
- The journey in `docs/acceptance/end-to-end-journeys.md` (journey 1) is demonstrable.

# Design: Secure multi-project foundations

## Context
ArchTwin requires an architect-first, secure, evidence-driven workflow. This increment implements the requirements in its `specs/` folder. The target platform architecture is in `docs/architecture/SOLUTION_ARCHITECTURE.md`, source-of-truth data semantics in `docs/architecture/DATA_MODEL.md`, and security constraints in `docs/security/THREAT_MODEL.md`.

## Decisions
- Build with Python 3.12+/FastAPI asyncio modules, PostgreSQL canonical state and scoped background workers; UI is React/Vite/shadcn/ui.
- All modules execute under identity/project scopes, gated by typed feature flags; protected operations always require Cerbos authorization.
- Source observations are immutable and independently distinguish desired, planned, code-derived, runtime and inferred evidence.
- All AI calls use LiteLLM → OpenAI in iteration one, with Langfuse tracing; no direct OpenAI SDK outside gateway. Support future on-prem endpoints by model alias, not by provider-specific business logic.

## Implementation design

## Modules and persistence
`org`, `project`, `identity`, `policies`, `flags`, `audit`, `events`, `llm_gateway`, `ui_shell` are independent Python packages with explicit ports. Transaction-scoped `RequestContext(principal, org_id, project_id?, env_id?, policy_revision, trace_id)`. Avoid module circular imports. Database: orgs/projects/environments, memberships, grants, flags/revisions, audit, outbox; all records scoped.

## API and UI vertical slice
Project wizard → select environment → project home → view members → turn a nonsecurity flag on/off → inspect audit. No model call is necessary for project creation. OIDC PKCE in React and validated JWT at the FastAPI boundary. Cerbos CheckResources on commands and checked-filter list reads. No impersonation of org admin by client claims.

## LLM gateway configuration
Deploy LiteLLM and Langfuse with environment-only credentials, scoped internal model key and project-level spend limit. Use Horizon-compatible OpenAI aliases for v1; do not initialize direct SDK. AI feature flags off until phase 06, but integration/telemetry smoke tests available behind admin-only diagnostics. Errors propagate with trace ID. No tracing of prompt bodies by default.

## Failure and abuse cases
Expired JWT, false audience, PDP outage, revoked memberships, last owner deletion, project A/B query, flag-off direct API call, queued job after disable, connector secret in log, outbox rollback, cancellation. See `docs/security/THREAT_MODEL.md`.


## Interfaces and persistence
- Changes flow through authoritative FastAPI service methods and PostgreSQL transactional outbox; async workers are idempotent.
- Public API contracts live in `docs/api/`; provider contracts in `docs/connectors/`; feature flags in `docs/feature-flags/`.
- No cross-tenant/project read, cache, vector result or AI context is permitted without current authorization and explicit federation grant where required.

## Testing and rollout
- Implement every Given/When/Then scenario in this phase and deliberate denial/failure tests.
- Keep write-back disabled until separately reviewed; use pilot-specific flags and observe metrics.
- Reconcile or revert via flags and explicit rollback after an error; retain immutable history and audit logs.

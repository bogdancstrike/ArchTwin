# Design: Continuous drift and early-warning intelligence

## Context
ArchTwin requires an architect-first, secure, evidence-driven workflow. This increment implements the requirements in its `specs/` folder. The target platform architecture is in `docs/architecture/SOLUTION_ARCHITECTURE.md`, source-of-truth data semantics in `docs/architecture/DATA_MODEL.md`, and security constraints in `docs/security/THREAT_MODEL.md`.

## Decisions
- Build with Python 3.12+/FastAPI asyncio modules, PostgreSQL canonical state and scoped background workers; UI is React/Vite/shadcn/ui.
- All modules execute under identity/project scopes, gated by typed feature flags; protected operations always require Cerbos authorization.
- Source observations are immutable and independently distinguish desired, planned, code-derived, runtime and inferred evidence.
- All AI calls use LiteLLM → OpenAI in iteration one, with Langfuse tracing; no direct OpenAI SDK outside gateway. Support future on-prem endpoints by model alias, not by provider-specific business logic.

## Implementation design

## Three-way rule engine
Input `{desired_snapshot, code_snapshot, runtime_snapshot, environment, authority_tiers, connector_freshness}`. Determine rule candidate only from verifiable facts: element missing/added, edge changed, protocol changed, contract incompatible, ownership/security boundary changed, unknown due to insufficient coverage. Stable rule ID + graph entity refs form drift identity.

## Alert pipeline
Webhook/watch -> incremental snapshot update -> deterministic drift rules -> suppression check -> priority score -> auditable finding -> authorized SSE/email/webhook. Aggregation and debounce prevent floods. A full reconcile regularly guards against missed events.

## False-positive controls
- Source unavailable = UNKNOWN; no deletion alert.
- Source with partial permissions = INCOMPLETE; do not assert complete topology.
- First scan = observe only until baseline captured.
- Dynamic/reflection paths have lower confidence; manual review before high-severity alerts.
- Temporal grace windows for progressive deployments, recreate UIDs and phased rollouts.

## Measurement
Define detection latency from provider event receipt (not real-world change time if provider doesn't signal). Report mean/p95, false-positive rate on labeled fixtures, alert volume by connector and freshness ratio. Never promise sub-second drift without real-time evidence.


## Interfaces and persistence
- Changes flow through authoritative FastAPI service methods and PostgreSQL transactional outbox; async workers are idempotent.
- Public API contracts live in `docs/api/`; provider contracts in `docs/connectors/`; feature flags in `docs/feature-flags/`.
- No cross-tenant/project read, cache, vector result or AI context is permitted without current authorization and explicit federation grant where required.

## Testing and rollout
- Implement every Given/When/Then scenario in this phase and deliberate denial/failure tests.
- Keep write-back disabled until separately reviewed; use pilot-specific flags and observe metrics.
- Reconcile or revert via flags and explicit rollback after an error; retain immutable history and audit logs.

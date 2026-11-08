# Design: Enterprise operations and extensibility

## Context
ArchTwin requires an architect-first, secure, evidence-driven workflow. This increment implements the requirements in its `specs/` folder. The target platform architecture is in `docs/architecture/SOLUTION_ARCHITECTURE.md`, source-of-truth data semantics in `docs/architecture/DATA_MODEL.md`, and security constraints in `docs/security/THREAT_MODEL.md`.

## Decisions
- Build with Python 3.12+/FastAPI asyncio modules, PostgreSQL canonical state and scoped background workers; UI is React/Vite/shadcn/ui.
- All modules execute under identity/project scopes, gated by typed feature flags; protected operations always require Cerbos authorization.
- Source observations are immutable and independently distinguish desired, planned, code-derived, runtime and inferred evidence.
- All AI calls use LiteLLM → OpenAI in iteration one, with Langfuse tracing; no direct OpenAI SDK outside gateway. Support future on-prem endpoints by model alias, not by provider-specific business logic.

## Implementation design

## Operations
PostgreSQL HA, object storage durability, Temporal worker scaling, scoped connection pools, backup/restore verification, disaster recovery and safe tenant deletion. Observability for scanning lag, drift freshness, API latency, LLM spend, backlog and graph query cost.

## Governance
Cross-project metrics without raw data leakage; independent ADR/baseline approval, review comments, portfolio security overlays, policy/version review. Connector plugins signed/approved, sandboxed and scoped. Stable public OpenAPI and exports.

## Capacity
Begin with 3–10 services per project; test 5k-node graphs and 50 projects before claiming enterprise scale. Benchmark query path, RLS, Cerbos policy plan translation, Kafka lag, connector quotas and consistency after worker failure.

## Migration and supportability
Versioned PostgreSQL migrations, compatibility rules, encrypted backups, concise runbooks, staged feature flag rollout, audit export/verifier and privacy deletion plan.


## Interfaces and persistence
- Changes flow through authoritative FastAPI service methods and PostgreSQL transactional outbox; async workers are idempotent.
- Public API contracts live in `docs/api/`; provider contracts in `docs/connectors/`; feature flags in `docs/feature-flags/`.
- No cross-tenant/project read, cache, vector result or AI context is permitted without current authorization and explicit federation grant where required.

## Testing and rollout
- Implement every Given/When/Then scenario in this phase and deliberate denial/failure tests.
- Keep write-back disabled until separately reviewed; use pilot-specific flags and observe metrics.
- Reconcile or revert via flags and explicit rollback after an error; retain immutable history and audit logs.

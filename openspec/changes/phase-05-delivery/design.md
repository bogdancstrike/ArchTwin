# Design: Plans, task execution and delivery alignment

## Context
ArchTwin requires an architect-first, secure, evidence-driven workflow. This increment implements the requirements in its `specs/` folder. The target platform architecture is in `docs/architecture/SOLUTION_ARCHITECTURE.md`, source-of-truth data semantics in `docs/architecture/DATA_MODEL.md`, and security constraints in `docs/security/THREAT_MODEL.md`.

## Decisions
- Build with Python 3.12+/FastAPI asyncio modules, PostgreSQL canonical state and scoped background workers; UI is React/Vite/shadcn/ui.
- All modules execute under identity/project scopes, gated by typed feature flags; protected operations always require Cerbos authorization.
- Source observations are immutable and independently distinguish desired, planned, code-derived, runtime and inferred evidence.
- All AI calls use LiteLLM → OpenAI in iteration one, with Langfuse tracing; no direct OpenAI SDK outside gateway. Support future on-prem endpoints by model alias, not by provider-specific business logic.

## Implementation design

## Planning semantics
Project roadmap includes capability, initiative, milestone, architecture change, ADR, requirement and execution task. External Jira/Taiga status is a separate state axis from code evidence, CI artifact and runtime deployment. Use explicit mapping workflows, not AI-only fuzzy linking.

## Sync behavior
Taiga/Jira/GitLab/GitHub connectors ingest issues/tasks into canonical work-item views with immutable source refs and version. Status mappings are per connector/project and versioned. Conflict handling preserves both revisions and requests a decision. Write-back is OFF until role+feature flag+preview+approval; use idempotency key and audit.

## Proof of implementation
Display planned, underway, merged, built, deployed, observed, verified stages; link artifact chain from issue -> MR/PR -> commit SHA -> release -> workload/image digest -> architecture edge verification. If an issue is Done but no runtime evidence, show `Unverified deployment`.

## Quality gates
CI architecture checks start report-only; only scoped, deterministic, review-approved policies can block. No LLM classification can block a release directly.


## Interfaces and persistence
- Changes flow through authoritative FastAPI service methods and PostgreSQL transactional outbox; async workers are idempotent.
- Public API contracts live in `docs/api/`; provider contracts in `docs/connectors/`; feature flags in `docs/feature-flags/`.
- No cross-tenant/project read, cache, vector result or AI context is permitted without current authorization and explicit federation grant where required.

## Testing and rollout
- Implement every Given/When/Then scenario in this phase and deliberate denial/failure tests.
- Keep write-back disabled until separately reviewed; use pilot-specific flags and observe metrics.
- Reconcile or revert via flags and explicit rollback after an error; retain immutable history and audit logs.

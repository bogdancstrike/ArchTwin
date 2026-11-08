# Design: Living diagrams and architecture knowledge

## Context
ArchTwin requires an architect-first, secure, evidence-driven workflow. This increment implements the requirements in its `specs/` folder. The target platform architecture is in `docs/architecture/SOLUTION_ARCHITECTURE.md`, source-of-truth data semantics in `docs/architecture/DATA_MODEL.md`, and security constraints in `docs/security/THREAT_MODEL.md`.

## Decisions
- Build with Python 3.12+/FastAPI asyncio modules, PostgreSQL canonical state and scoped background workers; UI is React/Vite/shadcn/ui.
- All modules execute under identity/project scopes, gated by typed feature flags; protected operations always require Cerbos authorization.
- Source observations are immutable and independently distinguish desired, planned, code-derived, runtime and inferred evidence.
- All AI calls use LiteLLM → OpenAI in iteration one, with Langfuse tracing; no direct OpenAI SDK outside gateway. Support future on-prem endpoints by model alias, not by provider-specific business logic.

## Implementation design

## Architecture graph
PostgreSQL canonical nodes/edges with temporal validity; source observations carry their original identifiers. Baseline approval creates immutable desired graph version. A code-derived or runtime snapshot cannot silently mutate approved intent.

## Diagram studio
C4 system context, container, component, landscape, deployment; data flow, event flow, sequence. Generate view from queries and store its layout separately from the underlying model. Use React Flow for interactions and table alternative for accessibility. Export Structurizr DSL/Mermaid and maintain stable element references; diagram import may require user-assisted mapping when reverse parsing is lossy.

## Documents and decisions
Docling imports PDF/DOCX; extracted passages are evidence. Generation always creates a draft, diff and citation coverage report; reviewers approve publication. ADR accepted versions immutable, supersession explicit. Source-driven regen never overwrites handcrafted prose without diff and acceptance.

## Integrity
Graph and exported diagrams must be reproducible from pinned snapshot + layout versions. Test stale evidence warnings, manual overrides, ACL in export, and graph relationship conflicts.


## Interfaces and persistence
- Changes flow through authoritative FastAPI service methods and PostgreSQL transactional outbox; async workers are idempotent.
- Public API contracts live in `docs/api/`; provider contracts in `docs/connectors/`; feature flags in `docs/feature-flags/`.
- No cross-tenant/project read, cache, vector result or AI context is permitted without current authorization and explicit federation grant where required.

## Testing and rollout
- Implement every Given/When/Then scenario in this phase and deliberate denial/failure tests.
- Keep write-back disabled until separately reviewed; use pilot-specific flags and observe metrics.
- Reconcile or revert via flags and explicit rollback after an error; retain immutable history and audit logs.

# Design: Discovery and connected data

## Context
ArchTwin requires an architect-first, secure, evidence-driven workflow. This increment implements the requirements in its `specs/` folder. The target platform architecture is in `docs/architecture/SOLUTION_ARCHITECTURE.md`, source-of-truth data semantics in `docs/architecture/DATA_MODEL.md`, and security constraints in `docs/security/THREAT_MODEL.md`.

## Decisions
- Build with Python 3.12+/FastAPI asyncio modules, PostgreSQL canonical state and scoped background workers; UI is React/Vite/shadcn/ui.
- All modules execute under identity/project scopes, gated by typed feature flags; protected operations always require Cerbos authorization.
- Source observations are immutable and independently distinguish desired, planned, code-derived, runtime and inferred evidence.
- All AI calls use LiteLLM → OpenAI in iteration one, with Langfuse tracing; no direct OpenAI SDK outside gateway. Support future on-prem endpoints by model alias, not by provider-specific business logic.

## Implementation design

## Architecture
Provider adapter -> bounded fetch -> immutable raw object -> normalization -> source observation -> canonical identity reconciliation -> outbox `inventory.changed`. Implement webhook ingress with signature verification and provider-scoped deduplication. Polling and full reconcile handle missed events.

## Supported P1
GitHub, GitLab, Kubernetes, PostgreSQL and Kafka metadata, HTTP OpenAPI, Docling file uploads. Taiga/Jira read-only work sync is important for phase 05; implement basic adapters here behind independent flags. Docker Swarm optional P2, then cloud/other DB families. Never use personal admin credentials for discovery.

## Extraction strategies
Source language analyzers use Tree-sitter and framework-specific parsers (Spring annotations, FastAPI routes, configs) as confidence-ranked plugins; avoid claiming complete program analysis. Match static to runtime through declared mappings, labels, names and repository metadata; ambiguous matches are reviewable. For Kafka producers inference, preserve uncertainty.

## Data contracts
Stable source key, provider revision, content hash, mapping version, captured timestamp, parsed evidence path/line, validity and confidence. Do not discard conflicting observations. Per-source freshness budget determines whether absence is meaningful.

## Hard failures
Provider 429 / cursor invalid / lost hook / token revoked / DNS SSRF / malicious doc / partial pagination / language parser crash / reconciliation while webhook arrives. All retries bounded and idempotent.


## Interfaces and persistence
- Changes flow through authoritative FastAPI service methods and PostgreSQL transactional outbox; async workers are idempotent.
- Public API contracts live in `docs/api/`; provider contracts in `docs/connectors/`; feature flags in `docs/feature-flags/`.
- No cross-tenant/project read, cache, vector result or AI context is permitted without current authorization and explicit federation grant where required.

## Testing and rollout
- Implement every Given/When/Then scenario in this phase and deliberate denial/failure tests.
- Keep write-back disabled until separately reviewed; use pilot-specific flags and observe metrics.
- Reconcile or revert via flags and explicit rollback after an error; retain immutable history and audit logs.

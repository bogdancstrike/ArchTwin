# Design: Grounded AI and cross-platform design

## Context
ArchTwin requires an architect-first, secure, evidence-driven workflow. This increment implements the requirements in its `specs/` folder. The target platform architecture is in `docs/architecture/SOLUTION_ARCHITECTURE.md`, source-of-truth data semantics in `docs/architecture/DATA_MODEL.md`, and security constraints in `docs/security/THREAT_MODEL.md`.

## Decisions
- Build with Python 3.12+/FastAPI asyncio modules, PostgreSQL canonical state and scoped background workers; UI is React/Vite/shadcn/ui.
- All modules execute under identity/project scopes, gated by typed feature flags; protected operations always require Cerbos authorization.
- Source observations are immutable and independently distinguish desired, planned, code-derived, runtime and inferred evidence.
- All AI calls use LiteLLM → OpenAI in iteration one, with Langfuse tracing; no direct OpenAI SDK outside gateway. Support future on-prem endpoints by model alias, not by provider-specific business logic.

## Implementation design

## Bounded retrieval then AI, not unconstrained agents
Call `authorize(federation, projects, environments)` before fetching any graph/document. Generate a signed/hashed context manifest with source IDs, confidence, freshness and gaps. Use deterministic graph tools for paths and contract lookup; LiteLLM only for synthesis and trade-off generation; Langfuse for sanitized traces and evals.

## A/B integration design contract
For two authorized projects: (1) inventory interfaces/contracts/trust boundaries; (2) request missing constraints when essential or state assumptions; (3) generate at least two options with tradeoff grid, C4/sequence diagrams, API/event sketches, authz/authn and data ownership, failure/consistency/cost; (4) generate ADR + task drafts; (5) user reviews and explicitly applies proposals. Cross-project data is not copied without grant and retention review.

## What-if and blast radius
Structural dependency paths bounded by hops/node count, scenario branch snapshots, deterministic graph effects. LLM MAY explain but cannot invent runtime probabilities or authorize changes. Show unknown nodes and confidence.

## Model release gates
Reuse Horizon's OpenAI aliases in LiteLLM; enforce profile capability/price validation. Run Langfuse golden evaluations for source grounding, prompt injection, cross-tenant isolation, diagrams and A/B design completeness. vLLM route exists only as future profile; disabled in initial iteration.


## Interfaces and persistence
- Changes flow through authoritative FastAPI service methods and PostgreSQL transactional outbox; async workers are idempotent.
- Public API contracts live in `docs/api/`; provider contracts in `docs/connectors/`; feature flags in `docs/feature-flags/`.
- No cross-tenant/project read, cache, vector result or AI context is permitted without current authorization and explicit federation grant where required.

## Testing and rollout
- Implement every Given/When/Then scenario in this phase and deliberate denial/failure tests.
- Keep write-back disabled until separately reviewed; use pilot-specific flags and observe metrics.
- Reconcile or revert via flags and explicit rollback after an error; retain immutable history and audit logs.

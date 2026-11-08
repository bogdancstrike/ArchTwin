# Design: Grounded AI and cross-platform design

## Context
Implements `specs/` of this change. AI architecture: `docs/ai/AI_ARCHITECTURE.md`; evaluation plan: `docs/ai/EVALUATION_PLAN.md`; model policy: `docs/ai/MODEL_PROFILES.yaml`. ADR-0005 (LiteLLM + Langfuse) applies.

## Goals / Non-goals
- **Goals:** scoped retrieval → grounded generation → citation validation; user-selectable models; federation grants; deterministic impact analysis; eval-gated rollout.
- **Non-goals:** autonomous agents with infrastructure access, AI deciding authorization, AI-detected drift, on-prem models in v1.

## Request pipeline
```
user question (+ selected model, default gpt-6-luna)
 → flags + budget check (reject before any model call)
 → authorize scopes (projects, environments, federation grants)  — Cerbos
 → deterministic tools collect evidence (graph queries, paths, contracts, passages)  — scoped SQL
 → evidence pack {evidence_id, source, revision, observed_at, freshness, confidence} + manifest hash
 → LiteLLM (Responses API, structured output schema per response type) → Langfuse trace
 → validate: every claim cites an evidence_id from the pack; unknown IDs ⇒ claim marked unsupported/removed
 → store PromptRun (model alias, manifest hash, policy revision) → stream to UI (SSE)
 → "Apply" = separate authorized command (never from the model)
```

## Decisions

| # | Decision | Adopted OSS | Notes |
|---|---|---|---|
| D1 | Server-owned deterministic tools only (`get_architecture_snapshot`, `find_dependency_paths`, `get_contract`, `diff_graph`, `get_work_status`, `get_source_passage`); strict JSON-schema validation; allowlist per operation | `openai` SDK via LiteLLM | No SQL/shell tools for the model |
| D2 | Retrieval: graph first (exact), passages second via PostgreSQL FTS + pgvector, both pre-filtered by scope | pgvector | Qdrant only if measured need (ADR-0002) |
| D3 | Untrusted text wrapped and labelled as data (spotlighting); system prompts never include secrets | — | Injection corpus in evals |
| D4 | User model choice per conversation/request from `/ai/models`; server validates against allowlists; alias recorded on PromptRun + trace | LiteLLM | Default `gpt-6-luna`; `gpt-6-terra`, `gpt-6-sol` selectable |
| D5 | Federation grants are bilateral, scoped by relation types and data classes, expiring; evaluated per query; revocation invalidates caches and saved answers | Cerbos | — |
| D6 | Impact analysis = bounded traversal (hops, node cap, time budget) with networkx on a scoped subgraph; scenarios are copy-on-write overlays on a snapshot | networkx | LLM only explains results |
| D7 | Integration designer output schema: options[] (≥2 when viable) × criteria (contracts, authn/z, ownership, latency, consistency, failure modes, idempotency, capacity, reachability, ops burden), unknowns[], diagrams[], adr_draft, task_drafts[] | Pydantic | — |
| D8 | AI-drafted diagrams are emitted as a structured view spec (nodes, edges, view type) — **not** raw SVG — and rendered by the phase-03 diagram-design renderer; the diagram-design rules (focal ≤2, ≤9 primary nodes, type selection) are part of the instructions and the linter gates the result | diagram-design system | Keeps AI output safe (no injected markup) and visually consistent |
| D9 | Evals in Langfuse datasets/experiments per selectable model; optional promptfoo red-team in CI; thresholds gate the model picker and `ai.*` flags | Langfuse, promptfoo | — |
| D10 | Budgets: per-project token/cost caps checked before calls; cancellation aborts upstream; costs priced identically in LiteLLM and ArchTwin (as Horizon) | LiteLLM | — |

## Risks / trade-offs
| Risk | Mitigation |
|---|---|
| Hallucinated facts | citation validation, unsupported-claim marking, eval thresholds |
| Injection via READMEs/issues | spotlighting, tool allowlist, scope fixed before generation, red-team suite |
| Cost spikes | budgets, concurrency caps, cheaper default model, caching of evidence packs (scope + ACL revision in key) |
| Different models behave differently | per-model eval runs; model shown next to every answer |

## Rollback
Disable `ai.*` / module flags; remove a model from the allowlist; deterministic features unaffected.

## Open questions
- Capabilities/prices of `gpt-6-terra` and `gpt-6-sol` must be verified at deployment; until then they stay hidden from the picker.

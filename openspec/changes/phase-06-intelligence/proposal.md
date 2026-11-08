# Proposal: Grounded AI and cross-platform design

## Why
Architects repeatedly ask "how do I connect platform A and B?", "what breaks if topic X goes away?", "is service Y really running?". Answering takes days of reading code, diagrams and tickets. With phases 01–05 providing scoped, evidenced architecture, AI can now produce **grounded** answers, alternatives, diagrams and ADR drafts — with citations, clear uncertainty, and no ability to change anything without approval.

Users affected: enterprise and solution architects, principal engineers, security architects.

## What Changes
- Add **Grounded AI architecture copilot** (`architecture-assistant`).
- Add **Project federation and cross-platform graph** (`cross-project-federation`).
- Add **Cross-platform integration design assistant** (`integration-designer`).
- Add **What-if simulation and blast-radius analysis** (`impact-analysis`).
- Add **AI quality, security and model flexibility** (`ai-evaluations`).

## Impact
- **Modules:** `intelligence` (evidence packs, tool router, answer validation), `federation`, `impact`, `evals`.
- **Tables:** prompt_runs (model alias chosen by the user, budgets, evidence manifest hash, Langfuse trace ID), evidence_packs, federation_grants, scenarios (branches), eval_datasets/eval_runs.
- **APIs:** `/ai/models`, `/ai/ask` (SSE), `/ai/integration-design`, `/scenarios`, `/federation-requests`, `/evals/runs`.
- **Adopted OSS:** LiteLLM, Langfuse (datasets, experiments, scores), `openai` SDK (Responses API via LiteLLM), Pydantic structured outputs, networkx for path/blast-radius algorithms, pgvector + PostgreSQL FTS for passage retrieval, promptfoo (optional, CI red-team), diagram-design system for AI-drafted diagrams.
- **Flags:** `module.architecture-assistant`, `module.cross-project-federation`, `module.integration-designer`, `module.impact-analysis`, `module.ai-evaluations`, `ai.*`, `projects.federation`.

## Dependencies
Phases 01–05 (phase 04/05 optional for some answers; the assistant states when that evidence is absent).

## Security risks
Prompt injection from ingested text, cross-project leakage through retrieval/caches/saved answers, hallucinated facts presented as evidence, runaway cost, unauthorized writes via "apply".

## Rollout and rollback
AI flags OFF by default per org/project; enabled first for the fixture, then a pilot project. A model appears in the picker only after it passes the evaluation thresholds. Rollback: disable `ai.*` flags — all deterministic features keep working.

## Success
- Golden datasets pass thresholds (grounding, citation validity, injection resistance, A/B integration completeness) for each selectable model (Luna default, Terra, Sol).
- Zero cross-project leaks in the red-team suite; zero writes without approval.
- A/B integration journey: ≥2 options, trade-off matrix, C4 + sequence diagrams (diagram-design conformant), ADR draft, task drafts — all citing evidence and listing unknowns.

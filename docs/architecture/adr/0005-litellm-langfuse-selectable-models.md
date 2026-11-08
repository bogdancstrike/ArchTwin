# ADR-0005: LiteLLM + Langfuse, OpenAI first, user-selectable models

- **Status:** Accepted (planning baseline)
- **Date:** 2026-11-08

## Context and problem
AI must be provider-portable, cost-controlled, observable and safe; users want to choose models.

## Decision
All AI traffic goes through **LiteLLM** (the only holder of provider keys); **Langfuse** traces and evaluates. v1 models: `gpt-6-luna` (**default**), `gpt-6-terra`, `gpt-6-sol` (user-selectable per conversation/request, filtered by org/project allowlists and eval thresholds), `gpt-5.6-luna` fallback, `text-embedding-3-large`. Future vLLM/local models are LiteLLM configuration. Retries at one layer only.

## Alternatives considered
- Direct provider SDKs in services — rejected: key sprawl, lock-in.
- Fixed single model — rejected: users need choice; evals make choice safe.

## Consequences
- Zero-token CI with a fake LLM mode.
- Every PromptRun records model alias and evidence manifest.
- Prices pinned in LiteLLM and ArchTwin so cost ledgers agree.

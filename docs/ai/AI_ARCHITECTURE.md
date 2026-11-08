# AI architecture — OpenAI-first, portable by design

## Provider topology
**API/worker → project AI policy → LiteLLM Proxy → OpenAI** in v1, with **Langfuse** capturing correlation, tokens, model version, cost, latency, error and human evaluation metadata. All AI application code uses a provider-neutral `AiGateway` interface and task-specific capability profiles.

**Reference to existing Horizon configuration** (`bogdancstrike/horizon`, `deploy/litellm/config.yaml`, `backend/horizon/config.py` reviewed 2026-11-07): Horizon defaults to `gpt-6-luna` with `medium` reasoning effort, offers `gpt-5.6-luna`, and uses `text-embedding-3-large` with a configured 1024-dimensional output. ArchTwin uses the same *aliases as a starting point*, but model availability, model-supported parameters, token limits and pricing MUST be validated at deployment, not blindly copied.

## Model profiles (config, not provider-coupled code)
| Profile | V1 alias | Tasks | Requirements |
|---|---|---|---|
| `architecture-reasoning` | **user-selected**: gpt-6-luna (default), gpt-6-terra, gpt-6-sol | cross-project solution design, ADR alternatives, architecture reviews | tool calling, structured output, medium reasoning when supported |
| `architecture-fast` | gpt-6-luna initially | summaries, constrained labeling, technical clarifications | low latency, structured output |
| `architecture-fallback` | gpt-5.6-luna | outage response if approved | same data policy, explicit fallback audit |
| `architecture-embedding` | text-embedding-3-large | optional document/architecture search vectors | verified dimensions, embedding version tracking |

### User-selectable models
Users pick the chat model per conversation or request from a model picker (Luna — default, Terra, Sol). The list comes from `GET /api/v1/ai/models`, which returns only aliases that (a) are registered in LiteLLM, (b) passed capability validation (tool calling, structured output, context size) and (c) are allowed by the org and project allowlists. Precedence: per-request > user preference > project default > org default > `gpt-6-luna`. The server re-validates the choice on every call; the chosen alias is stored on the `PromptRun`, shown next to the answer and sent to Langfuse so quality and cost can be compared per model. System tasks (`architecture-fast`, embeddings, eval judges) are not user-selectable.

No OpenAI provider client is imported into business services. OpenAI keys are mounted **only** into LiteLLM; workers use scoped gateway keys. No automatic fallback across data residency/privacy policy boundaries.

## Langfuse: useful without compromising privacy
- Trace each AI action with trace/span IDs, organization/project hashed or opaque identifiers, model profile, token counts, latency, cost, sources count, policy and outcome.
- Trace content is OFF for sensitive/private workspaces by default; allow opt-in with proper role and retention; redact connector tokens, secrets, PII and private topology.
- Use Langfuse experiments/evaluations for grounding, diagram correctness, prompt injection, integration recommendation consistency and cost.
- Treat Langfuse as observability/evaluation, not source of authorization, canonical cost policy or architecture truth.

## Retrieval and generation contract
1. Evaluate authentication, Cerbos scopes and project/environment/federation grants.
2. Query exact graph entities and source observations using scoped filters; expand bounded dependencies.
3. Retrieve supplementary doc passages only after ACL filtering; classify sources and include time/freshness.
4. Assemble evidence pack with `evidence_id` and provenance; guard tokens, cost and context limits.
5. Generate structured response via LiteLLM. Supported response types: answer with citations, alternatives matrix, diagram draft, ADR draft, task suggestions and clarifying open questions.
6. Validate all references against the evidence pack; unsupported claims are marked uncertain or rejected. Apply sanitization and policy checks to output.
7. Store result with snapshot ID, used source IDs and policy revision. Revalidate before reopening shared answers.
8. Apply? Only explicit human action, separate `CheckResources`, feature flag, command validation and audit. Remote task write-back requires additional approval.

## Tool use
Start with **server-owned deterministic tools**: `get_project`, `get_architecture_snapshot`, `list_interfaces`, `diff_graph`, `get_contract`, `get_work_status`, `find_dependency_paths`, `get_source_passage`. Treat model-generated tool names/arguments as untrusted; strict schema validation, policy before execution. Avoid turning AI into arbitrary SQL executor or container shell.

## Prompt injection controls
- Inputs from repository docs, issue descriptions, external websites, PDFs, comments and source metadata are untrusted; label as evidence text not agent instruction.
- Never expose connector credentials or system prompts to models.
- No tool's own text may enlarge a user's permissions or a project's scope.
- Test adversarial source docs asking for a cross-project secret, tool execution or unauthorized export.

## Future local model support (not MVP behavior)
Add an allowed backend to LiteLLM e.g. `openai-compatible` / vLLM, register `architecture-reasoning-local`, test tool calling and structured responses, quality/cost evaluation, switch by scoped project profile. Supports GPU allocation, KV/cache observability via a later infrastructure module. **Do not promise local models have parity** until benchmarks prove acceptance thresholds. Embedding provider changes require parallel versioned indexes and migration.

## Configuration & safety
See `docs/ai/litellm-config.example.yaml` and `docs/ai/MODEL_PROFILES.yaml`. These are templates with environment references only, not deployments. Keep retries at a single deliberate layer to avoid amplified charges (as in Horizon). Maintain abort/cancel and per-task budget controls.

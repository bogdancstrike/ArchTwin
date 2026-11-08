# LiteLLM, Langfuse and AI provider abstraction

## ADDED Requirements

### Requirement: LiteLLM-only AI egress
**Requirement ID:** `AT-LLM_GATEWAY-001`

Every generative AI and embedding request MUST go through the internal LiteLLM gateway; only its service possesses upstream OpenAI credentials.

#### Scenario: No direct access
- **GIVEN** a worker receives only the LiteLLM endpoint and scoped token
- **WHEN** it requests a completion
- **THEN** the request is mediated and billed through LiteLLM

#### Scenario: Direct provider call blocked
- **GIVEN** a service attempts to reach the provider API directly
- **WHEN** the request leaves the pod
- **THEN** network policy blocks it and no provider key exists in that service's environment

### Requirement: Horizon-aligned v1 defaults
**Requirement ID:** `AT-LLM_GATEWAY-002`

Initial model aliases MUST default to Horizon-compatible gpt-6-luna for reasoning (medium effort where supported), optional gpt-5.6-luna fallback and text-embedding-3-large for embeddings, with validated names and dimensions.

#### Scenario: Model misconfiguration
- **GIVEN** a model alias is unavailable
- **WHEN** an AI task begins
- **THEN** the job fails with actionable configuration error rather than silently switching providers

#### Scenario: Embedding dimension mismatch
- **GIVEN** the configured embedding dimension differs from the index dimension
- **WHEN** the service starts
- **THEN** startup health fails with an explicit configuration error

### Requirement: Langfuse telemetry
**Requirement ID:** `AT-LLM_GATEWAY-003`

LLM requests MUST emit correlated Langfuse traces with project/feature/cost/latency and redacted payload policy, including failures and model versions.

#### Scenario: Privacy mode
- **GIVEN** a project disables prompt payload retention
- **WHEN** a completion occurs
- **THEN** trace metadata is visible but sensitive content is not persisted

#### Scenario: Telemetry backend down
- **GIVEN** Langfuse is unavailable
- **WHEN** a completion runs
- **THEN** the completion succeeds, telemetry is buffered or dropped per policy and no request blocks on tracing

### Requirement: On-prem readiness
**Requirement ID:** `AT-LLM_GATEWAY-004`

Model selection MUST depend on capabilities, context, latency and privacy policy rather than provider-specific application code; future local endpoints MUST be configurable behind LiteLLM.

#### Scenario: Future vLLM
- **GIVEN** an admin registers an OpenAI-compatible on-prem endpoint
- **WHEN** a compatible project selects it
- **THEN** no domain service code changes are required

#### Scenario: Incompatible endpoint rejected
- **GIVEN** a registered local endpoint lacks tool calling
- **WHEN** a profile that requires tool calling selects it
- **THEN** profile validation fails before any user request is routed to it

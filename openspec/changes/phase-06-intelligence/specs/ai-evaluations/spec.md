# AI quality, security and model flexibility

## ADDED Requirements

### Requirement: Evaluation dataset
**Requirement ID:** `AT-AI_EVALUATIONS-001`

AI features MUST have regression datasets for diagram correctness, cited answers, unsupported assertions, prompt injection, integration recommendation quality and cost.

#### Scenario: New model
- **GIVEN** model alias changes
- **WHEN** CI evaluation runs
- **THEN** quality and cost deltas are compared before enabling rollout

#### Scenario: Regression blocks rollout
- **GIVEN** a new model alias lowers grounding below threshold
- **WHEN** evaluation completes
- **THEN** the rollout flag cannot be enabled without an explicit, audited override

### Requirement: Provider independence
**Requirement ID:** `AT-AI_EVALUATIONS-002`

Project model profiles MUST map via LiteLLM aliases and capabilities; local vLLM support MAY be added later without changing business domain contracts.

#### Scenario: Switch provider
- **GIVEN** approved local endpoint is configured in LiteLLM
- **WHEN** model profile selects it
- **THEN** architecture assistant continues using same API abstraction

#### Scenario: Fallback across policy boundary
- **GIVEN** the primary model fails and the only fallback violates data-residency policy
- **WHEN** a request is made
- **THEN** the request fails instead of falling back

### Requirement: Human override
**Requirement ID:** `AT-AI_EVALUATIONS-003`

No LLM output MUST directly authorize resource access, mutate accepted architecture, or execute deployments.

#### Scenario: Generated admin command
- **GIVEN** LLM suggests deleting an exposed service
- **WHEN** answer is delivered
- **THEN** no infrastructure change happens

#### Scenario: Tool call outside allowlist
- **GIVEN** the model emits a call to an unregistered tool
- **WHEN** the tool router receives it
- **THEN** the call is rejected and logged

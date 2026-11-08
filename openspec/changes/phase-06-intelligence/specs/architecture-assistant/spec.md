# Grounded AI architecture copilot

## ADDED Requirements

### Requirement: Bounded context
**Requirement ID:** `AT-ARCHITECTURE_ASSISTANT-001`

All architecture AI requests MUST be scoped by user, organization, projects, environments, approved sources and time range before retrieval.

#### Scenario: Unauthorized query
- **GIVEN** user asks about an inaccessible service
- **WHEN** assistant builds context
- **THEN** the inaccessible entity is not retrieved or summarized

#### Scenario: Injected instruction
- **GIVEN** a README tells the assistant to include another project
- **WHEN** the context is built
- **THEN** scope stays unchanged and the injection attempt is logged

### Requirement: Explain with sources
**Requirement ID:** `AT-ARCHITECTURE_ASSISTANT-002`

Answers MUST cite architecture records, source paths/lines, connector snapshots, ADRs or deployment evidence; uncertain or missing evidence MUST be stated.

#### Scenario: Unknown answer
- **GIVEN** no evidence proves a deployment
- **WHEN** user asks if it is running
- **THEN** assistant replies unknown with last observation time

#### Scenario: Invented citation
- **GIVEN** the model cites an evidence ID that is not in the evidence pack
- **WHEN** the response is validated
- **THEN** the claim is marked unsupported or removed before display

### Requirement: Architect workflows
**Requirement ID:** `AT-ARCHITECTURE_ASSISTANT-003`

Assistant MUST offer drafting of design alternatives, architecture diagrams, ADRs, reviews and task suggestions as proposals with preview/approval.

#### Scenario: Generated diagram
- **GIVEN** assistant drafts topology
- **WHEN** user reviews
- **THEN** canonical model remains unchanged until Apply authorized

#### Scenario: Apply without permission
- **GIVEN** a viewer opens an assistant proposal
- **WHEN** they click Apply
- **THEN** the command is denied by policy

### Requirement: Budget safety
**Requirement ID:** `AT-ARCHITECTURE_ASSISTANT-004`

Operations MUST enforce per-project token/cost budgets, rate limits, timeouts, cancellation and trace correlation via LiteLLM/Langfuse.

#### Scenario: Budget exceeded
- **GIVEN** project LLM spend cap is exhausted
- **WHEN** user requests generation
- **THEN** request is rejected before model call

#### Scenario: User cancels
- **GIVEN** a long generation is running
- **WHEN** the user cancels
- **THEN** the upstream request is aborted and only consumed tokens are billed

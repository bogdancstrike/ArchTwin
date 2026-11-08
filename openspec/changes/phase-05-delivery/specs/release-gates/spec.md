# Architecture-aware release checks

## ADDED Requirements

### Requirement: Non-blocking-first gates
**Requirement ID:** `AT-RELEASE_GATES-001`

The platform MUST offer architecture conformance checks in report-only mode first, followed by opt-in CI blocking per project/environment.

#### Scenario: Default policy
- **GIVEN** new project connects CI
- **WHEN** a drift is found
- **THEN** CI receives a warning rather than blocked deployment

#### Scenario: Blocking enabled by owner
- **GIVEN** a project owner enables blocking for prod with a deterministic rule
- **WHEN** a matching violation occurs
- **THEN** CI receives a failing result with the rule ID and evidence

### Requirement: Policy control
**Requirement ID:** `AT-RELEASE_GATES-002`

Blocking decisions MUST require deterministic documented rules, stable evidence and explicit owner-approved enablement.

#### Scenario: AI recommendation
- **GIVEN** LLM labels a deployment risky
- **WHEN** gate evaluates
- **THEN** only configured deterministic policy can block

#### Scenario: Unknown evidence does not block
- **GIVEN** the evidence needed by a blocking rule is stale
- **WHEN** the gate evaluates
- **THEN** the result is unknown and follows the configured fail-open or fail-closed policy, which is shown

### Requirement: Signed artifacts
**Requirement ID:** `AT-RELEASE_GATES-003`

Review results MUST be exportable as versioned artifacts with signed provenance and links to source commits and observed state.

#### Scenario: CI artifact
- **GIVEN** a check completes
- **WHEN** CI consumes the result
- **THEN** it can verify the exact assessment version

#### Scenario: Tampered result
- **GIVEN** a check result is modified after signing
- **WHEN** CI verifies it
- **THEN** verification fails

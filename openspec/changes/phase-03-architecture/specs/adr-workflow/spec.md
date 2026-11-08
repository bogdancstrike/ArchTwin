# Architecture decisions and review governance

## ADDED Requirements

### Requirement: ADR lifecycle
**Requirement ID:** `AT-ADR_WORKFLOW-001`

The system MUST manage proposed/accepted/rejected/superseded ADRs with context, decision drivers, options, trade-offs, consequences, owners and evidence.

#### Scenario: Supersede
- **GIVEN** an accepted ADR is replaced
- **WHEN** new ADR is approved
- **THEN** old ADR stays immutable and links to its successor

#### Scenario: Accepted ADR edit refused
- **GIVEN** an ADR is accepted
- **WHEN** a user edits its decision text
- **THEN** the edit is refused and a superseding draft is offered

### Requirement: Decision linkage
**Requirement ID:** `AT-ADR_WORKFLOW-002`

ADRs MUST reference affected elements, projects, requirements, risks and work items and MUST surface when an implementation contradicts an accepted decision.

#### Scenario: Contradiction
- **GIVEN** ADR mandates async events
- **WHEN** runtime integration uses synchronous HTTP
- **THEN** the mismatch is flagged for review

#### Scenario: Unknown runtime evidence
- **GIVEN** the runtime connector is stale
- **WHEN** conformance to an ADR is evaluated
- **THEN** the result is unknown rather than compliant

### Requirement: Review and sign-off
**Requirement ID:** `AT-ADR_WORKFLOW-003`

High-impact decisions MUST support configurable multi-party review, explicit approval and immutable decisions history.

#### Scenario: Self approval blocked
- **GIVEN** policy requires independent reviewer
- **WHEN** author tries to approve
- **THEN** approval is denied

#### Scenario: Valid independent approval
- **GIVEN** policy requires one independent reviewer
- **WHEN** a reviewer who is not the author approves
- **THEN** the ADR becomes accepted and immutable

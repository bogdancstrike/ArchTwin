# Drift scoring and lifecycle

## ADDED Requirements

### Requirement: Prioritization
**Requirement ID:** `AT-DRIFT_TRIAGE-001`

Findings MUST be scored using explicit impact factors such as criticality, exposure, environment, change magnitude, confidence and active incidents.

#### Scenario: Same change different criticality
- **GIVEN** prod payment path and dev test path both drift
- **WHEN** scores compute
- **THEN** the prod critical path receives higher priority with explanation

#### Scenario: Low confidence capped
- **GIVEN** a finding is based only on inferred evidence
- **WHEN** scores compute
- **THEN** its priority cannot exceed the configured cap for inferred evidence

### Requirement: Workflow
**Requirement ID:** `AT-DRIFT_TRIAGE-002`

Drift findings MUST support new, acknowledged, investigating, accepted, resolved and suppressed states, assignments, comments and linked changes.

#### Scenario: Resolve with evidence
- **GIVEN** a drift is marked resolved
- **WHEN** underlying mismatch persists
- **THEN** resolution requires new verified evidence or explicit exception

#### Scenario: Reopen on recurrence
- **GIVEN** a resolved finding's mismatch reappears
- **WHEN** the next evaluation runs
- **THEN** the same finding identity is reopened with history rather than duplicated

### Requirement: Traceable alerts
**Requirement ID:** `AT-DRIFT_TRIAGE-003`

Every finding MUST link to its baseline, observed data, rule version and relevant source changes.

#### Scenario: Investigate
- **GIVEN** a drift alert is opened
- **WHEN** architect expands evidence
- **THEN** they can inspect exact compared versions

#### Scenario: Evidence expired by retention
- **GIVEN** raw evidence of an old finding passed retention
- **WHEN** the finding is opened
- **THEN** metadata and hashes remain and the UI states that raw content expired

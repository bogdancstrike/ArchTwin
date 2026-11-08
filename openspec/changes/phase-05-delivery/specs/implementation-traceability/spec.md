# Implementation evidence and delivery tracking

## ADDED Requirements

### Requirement: Evidence chain
**Requirement ID:** `AT-IMPLEMENTATION_TRACEABILITY-001`

Requirements MUST trace to ADRs, architecture elements, Git commits/PRs/MRs, CI checks, work items and observed deployments.

#### Scenario: Implementation query
- **GIVEN** architect asks what is built for requirement R
- **WHEN** trace query runs
- **THEN** it shows evidence stages and gaps without equating merged code to deployed state

#### Scenario: Missing link reported
- **GIVEN** a requirement has no linked commit
- **WHEN** the trace query runs
- **THEN** the gap is listed explicitly instead of hidden

### Requirement: Status semantics
**Requirement ID:** `AT-IMPLEMENTATION_TRACEABILITY-002`

Status MUST distinguish planned, in-progress, implemented-in-code, built, deployed, observed, verified and rolled-back states.

#### Scenario: Code-only
- **GIVEN** a PR has merged but release is not deployed
- **WHEN** status computes
- **THEN** feature is marked implemented-in-code, not deployed

#### Scenario: Rollback detected
- **GIVEN** a deployed image digest is replaced by an older digest
- **WHEN** status computes
- **THEN** the change is marked rolled-back

### Requirement: Drift from plan
**Requirement ID:** `AT-IMPLEMENTATION_TRACEABILITY-003`

When accepted plans change, the platform MUST identify orphaned tasks, stale ADRs and implementation mismatches.

#### Scenario: Plan revision
- **GIVEN** a service planned for removal remains in active tasks
- **WHEN** plan changes
- **THEN** task/architecture mismatch appears in review

#### Scenario: No change, no noise
- **GIVEN** a plan edit only changes a description
- **WHEN** mismatch detection runs
- **THEN** no orphan or mismatch findings are created

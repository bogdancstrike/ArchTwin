# Desired, observed and implemented architecture drift

## ADDED Requirements

### Requirement: Drift baseline
**Requirement ID:** `AT-DRIFT_ENGINE-001`

For each project and environment the platform MUST compare declared architecture, code-observed architecture and runtime-observed architecture as distinct dimensions.

#### Scenario: Three-way discrepancy
- **GIVEN** diagram states Kafka, code calls REST and traces show REST
- **WHEN** scan executes
- **THEN** report identifies declared-versus-code/runtime drift rather than silently updating diagram

#### Scenario: No baseline
- **GIVEN** a project has no approved baseline
- **WHEN** drift evaluation runs
- **THEN** only code-versus-runtime comparison runs and declared-architecture drift is reported as not applicable

### Requirement: Drift taxonomy
**Requirement ID:** `AT-DRIFT_ENGINE-002`

Drift MUST classify missing/extra elements, relationship changes, protocol changes, ownership changes, contracts, security boundaries and freshness-related unknowns.

#### Scenario: Insufficient evidence
- **GIVEN** runtime watcher is stale
- **WHEN** drift evaluation runs
- **THEN** status is unknown, not absent

#### Scenario: Partial permissions
- **GIVEN** the connector can list only half of the namespaces
- **WHEN** drift evaluation runs
- **THEN** missing elements in unlisted namespaces are classified incomplete, not missing

### Requirement: Deterministic rules
**Requirement ID:** `AT-DRIFT_ENGINE-003`

Structural drift decisions MUST come from reproducible rules over normalized evidence; AI MAY explain or prioritize findings but MUST NOT invent detection facts.

#### Scenario: Repeat scan
- **GIVEN** same immutable snapshots are compared twice
- **WHEN** rules execute
- **THEN** drift IDs and classifications are stable

#### Scenario: Rule version change
- **GIVEN** a drift rule is upgraded to a new version
- **WHEN** the same snapshots are evaluated
- **THEN** findings record the new rule version and the old findings remain linked to the old version

### Requirement: Suppressions and acceptance
**Requirement ID:** `AT-DRIFT_ENGINE-004`

Users MUST be able to accept intended changes or apply time-bound, scoped suppressions with reasons, reviewers and expiry.

#### Scenario: Expired exception
- **GIVEN** a temporary suppression expires
- **WHEN** finding still exists
- **THEN** alert is eligible again

#### Scenario: Suppression scope
- **GIVEN** a suppression covers one edge in prod
- **WHEN** the same drift appears in staging
- **THEN** the staging finding is not suppressed

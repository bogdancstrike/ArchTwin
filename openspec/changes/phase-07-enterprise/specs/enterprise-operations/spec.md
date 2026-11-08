# Reliability, scale, backup and retention

## ADDED Requirements

### Requirement: SLOs
**Requirement ID:** `AT-ENTERPRISE_OPERATIONS-001`

The platform MUST publish availability, query latency, ingestion lag, drift time-to-detection, recovery and queue-depth SLO telemetry.

#### Scenario: Freshness alert
- **GIVEN** watcher misses freshness SLO
- **WHEN** SLO monitor runs
- **THEN** alert names degraded connector and project

#### Scenario: SLO burn alert
- **GIVEN** the error budget burns faster than the configured rate
- **WHEN** the monitor evaluates
- **THEN** operators receive a burn-rate alert

### Requirement: HA and recovery
**Requirement ID:** `AT-ENTERPRISE_OPERATIONS-002`

PostgreSQL, object storage and async workers MUST have documented backup, restore, recovery-point and recovery-time objectives with periodic exercises.

#### Scenario: Database restore
- **GIVEN** backup restoration is rehearsed
- **WHEN** verification executes
- **THEN** counts, checksums and access policies are validated

#### Scenario: Restore with missing key
- **GIVEN** the encryption key is unavailable during restore
- **WHEN** restore runs
- **THEN** the restore fails loudly instead of producing partially readable data

### Requirement: Retention
**Requirement ID:** `AT-ENTERPRISE_OPERATIONS-003`

Data retention, legal hold, connector deletion, GDPR-oriented exports and project deletion MUST respect org policy without leaking across tenants.

#### Scenario: Delete connector
- **GIVEN** a connector is removed
- **WHEN** retention worker executes
- **THEN** its secrets are revoked and eligible artifacts expire after policy checks

#### Scenario: Legal hold
- **GIVEN** a project is under legal hold
- **WHEN** deletion is requested
- **THEN** deletion is blocked and the hold is shown

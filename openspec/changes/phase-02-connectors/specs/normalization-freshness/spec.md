# Evidence normalization, confidence and freshness

## ADDED Requirements

### Requirement: Canonical mapping
**Requirement ID:** `AT-NORMALIZATION_FRESHNESS-001`

Raw connector data MUST be mapped to versioned canonical entity and relationship types with stable source IDs and explicit mapping versions.

#### Scenario: New adapter mapping
- **GIVEN** a GitLab response schema changes
- **WHEN** mapping fails validation
- **THEN** no malformed canonical records are committed

#### Scenario: Mapping version recorded
- **GIVEN** mapping version 2 is deployed
- **WHEN** new records are written
- **THEN** each record stores mapping version 2 while older records keep version 1

### Requirement: Provenance confidence
**Requirement ID:** `AT-NORMALIZATION_FRESHNESS-002`

Every discovered fact MUST store source confidence, observation freshness and authority tier; conflicting evidence MUST remain inspectable.

#### Scenario: Conflict
- **GIVEN** code declares HTTP but runtime observes Kafka
- **WHEN** graph reconciliation runs
- **THEN** both observations are retained and a conflict is surfaced

#### Scenario: Low confidence not promoted
- **GIVEN** a heuristic emits a relation with confidence 0.3
- **WHEN** the graph is built
- **THEN** the relation is shown as inferred and never as observed

### Requirement: Staleness budgets
**Requirement ID:** `AT-NORMALIZATION_FRESHNESS-003`

Source connectors MUST have configurable freshness SLAs and stale indicators; stale data MUST NOT be treated as current in AI answers.

#### Scenario: Stale deployment
- **GIVEN** Kubernetes cannot be queried for 24 hours
- **WHEN** architect asks about current deployment
- **THEN** answer labels state as last observed, not verified current

#### Scenario: Fresh source shown as current
- **GIVEN** the Kubernetes connector synced two minutes ago within its SLA
- **WHEN** the architect views deployments
- **THEN** the data is labelled current with its observation time

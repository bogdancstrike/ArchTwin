# Feature flags and kill switches

## ADDED Requirements

### Requirement: Feature flag hierarchy
**Requirement ID:** `AT-FEATURE_FLAGS-001`

The system MUST evaluate a typed flag catalog with precedence emergency-off > organization policy > project/environment override > role cohort > default.

#### Scenario: Emergency disable
- **GIVEN** a connector type is globally disabled
- **WHEN** a project previously enabled it
- **THEN** no new connector job of that type starts

#### Scenario: Security invariant cannot be disabled
- **GIVEN** an admin attempts to set security.cerbos_required to false
- **WHEN** the flag change is submitted
- **THEN** the change is rejected and audited

### Requirement: All major modules
**Requirement ID:** `AT-FEATURE_FLAGS-002`

Every major module, connector family, background watcher, AI operation and external write integration MUST have a registered feature flag, including UI discoverability and backend enforcement.

#### Scenario: Disabled module
- **GIVEN** AI assistant is disabled for a project
- **WHEN** the user calls its API directly
- **THEN** the server returns feature-disabled and spends no model tokens

#### Scenario: Unregistered flag
- **GIVEN** code checks a flag key that is not in the catalog
- **WHEN** the evaluation runs
- **THEN** the result is OFF and a catalog-violation metric is emitted

### Requirement: Auditable rollout
**Requirement ID:** `AT-FEATURE_FLAGS-003`

Changes MUST be audited, versioned, propagated within 15s in an operational target and reversible; queued tasks MUST recheck at execution time.

#### Scenario: Queued job disabled
- **GIVEN** a drift scan is queued
- **WHEN** its feature is disabled before execution
- **THEN** the scan is skipped safely with an audit status

#### Scenario: Stale cache on high-risk action
- **GIVEN** the flag cache revision is older than the propagation budget
- **WHEN** a high-risk action such as write-back evaluates its flag
- **THEN** the action is treated as disabled

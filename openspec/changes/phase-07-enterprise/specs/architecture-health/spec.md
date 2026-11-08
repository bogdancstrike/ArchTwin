# Architecture health and portfolio insights

## ADDED Requirements

### Requirement: Quality scorecards
**Requirement ID:** `AT-ARCHITECTURE_HEALTH-001`

Architecture health views MUST show evidence-backed metrics for drift, freshness, ownership, contract coverage, decisions, delivery traceability and policy compliance.

#### Scenario: Unknown metrics
- **GIVEN** a project has no runtime connector
- **WHEN** health dashboard renders
- **THEN** missing coverage is displayed, not implied healthy

#### Scenario: Metric definition shown
- **GIVEN** a scorecard metric is displayed
- **WHEN** the user opens its details
- **THEN** the formula, inputs and evidence coverage are shown

### Requirement: Trends
**Requirement ID:** `AT-ARCHITECTURE_HEALTH-002`

Users MUST compare architecture health over time, by environment and project, with drill-through to source evidence.

#### Scenario: Week comparison
- **GIVEN** two historical snapshots exist
- **WHEN** architect selects periods
- **THEN** metric calculation uses fixed definition and underlying evidence

#### Scenario: Definition changed
- **GIVEN** a metric definition changes
- **WHEN** trends across the change are shown
- **THEN** the chart marks the definition change instead of mixing values silently

### Requirement: Portfolio rollups
**Requirement ID:** `AT-ARCHITECTURE_HEALTH-003`

Portfolio rollups MUST only aggregate explicitly approved cross-project metrics and MUST NOT expose protected project-level rows.

#### Scenario: Portfolio permission
- **GIVEN** executive has aggregated access only
- **WHEN** they open portfolio
- **THEN** raw project evidence is not exposed

#### Scenario: Small-group suppression
- **GIVEN** an aggregate covers fewer projects than the minimum group size
- **WHEN** the portfolio renders
- **THEN** the value is suppressed to prevent inferring a single project

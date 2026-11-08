# What-if simulation and blast-radius analysis

## ADDED Requirements

### Requirement: Graph impact
**Requirement ID:** `AT-IMPACT_ANALYSIS-001`

The platform MUST compute explainable dependency paths and bounded transitive impact for change, outage or contract breakage scenarios.

#### Scenario: Delete topic
- **GIVEN** architect models loss of Kafka topic X
- **WHEN** simulation runs
- **THEN** impacted consumers are listed with evidence and unknown edges

#### Scenario: Traversal bound reached
- **GIVEN** the dependency graph exceeds the node cap
- **WHEN** simulation runs
- **THEN** results are truncated with an explicit truncation notice

### Requirement: Scenario branches
**Requirement ID:** `AT-IMPACT_ANALYSIS-002`

Users MUST create isolated scenario branches of architecture models with reversible changes and compare them to a baseline.

#### Scenario: What-if test
- **GIVEN** architect removes an API in a scenario
- **WHEN** views regenerate
- **THEN** production baseline is unchanged

#### Scenario: Scenario isolation between users
- **GIVEN** user X creates a private scenario
- **WHEN** user Y without access lists scenarios
- **THEN** the scenario is not visible

### Requirement: Bounded claims
**Requirement ID:** `AT-IMPACT_ANALYSIS-003`

Impact results MUST distinguish structural connectivity from measured runtime effects, and MUST NOT present simulated outcomes as incidents.

#### Scenario: No runtime metrics
- **GIVEN** impact graph suggests a path
- **WHEN** user asks outage probability
- **THEN** tool explains probability cannot be inferred

#### Scenario: Measured effect available
- **GIVEN** runtime metrics show actual error rates for a dependency
- **WHEN** impact is displayed
- **THEN** measured values are labelled as observed with their source and time

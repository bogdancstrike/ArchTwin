# Canonical architectural knowledge graph

## ADDED Requirements

### Requirement: Graph semantics
**Requirement ID:** `AT-ARCHITECTURE_GRAPH-001`

The system MUST model systems, services, modules, APIs, topics, databases, environments, teams, requirements, decisions, tasks, edges and evidence in versioned canonical semantics.

#### Scenario: Identity merge
- **GIVEN** two adapters discover the same service with matching authoritative keys
- **WHEN** normalization executes
- **THEN** one logical entity references two source observations

#### Scenario: Ambiguous identity
- **GIVEN** two services share a name but have different repositories and no authoritative key
- **WHEN** normalization executes
- **THEN** two entities are kept and a reviewable merge suggestion is raised

### Requirement: Relationship lifecycle
**Requirement ID:** `AT-ARCHITECTURE_GRAPH-002`

Architecture relationships MUST carry direction, type, environment, validity interval, asserted/observed origin, confidence and source references.

#### Scenario: Removed edge
- **GIVEN** service A stops consuming topic B
- **WHEN** a new scan runs
- **THEN** historical edge persists but is inactive in the latest snapshot

#### Scenario: Cross-project edge rejected
- **GIVEN** an edge references a node of another project without a federation grant
- **WHEN** it is written
- **THEN** the database constraint rejects it

### Requirement: Human model overlay
**Requirement ID:** `AT-ARCHITECTURE_GRAPH-003`

Architect-curated relationships and boundaries MUST be separated from inferred facts and runtime observations and require versioned review to change.

#### Scenario: Manual intent
- **GIVEN** an architect defines a planned HTTP dependency
- **WHEN** runtime has not observed it
- **THEN** the plan appears as planned, not deployed

#### Scenario: Scan cannot overwrite curation
- **GIVEN** an architect curated a boundary in the baseline
- **WHEN** a scan observes something different
- **THEN** the baseline stays unchanged and a drift candidate is created

# Diagram generation and visual architecture editing

## ADDED Requirements

### Requirement: Multi-view diagrams
**Requirement ID:** `AT-DIAGRAM_STUDIO-001`

The studio MUST render C4 context/container/component, system landscape, deployment, data-flow, event-flow and sequence views from the same canonical graph.

#### Scenario: Generate C4
- **GIVEN** a project graph contains systems and containers
- **WHEN** an architect chooses C4 Container
- **THEN** diagram draws only relevant elements with stable references

#### Scenario: Graph alternative
- **GIVEN** a diagram is open
- **WHEN** the user switches to the table view
- **THEN** the same elements and relations are listed in an accessible table

### Requirement: Round-trip safety
**Requirement ID:** `AT-DIAGRAM_STUDIO-002`

The studio MUST support versioned diagrams, human layout overrides, draft AI proposals and controlled Structurizr DSL/Mermaid exports, without overwriting hand-authored edits.

#### Scenario: Regenerate
- **GIVEN** the source graph changes after a manual layout edit
- **WHEN** the user regenerates
- **THEN** manual positions remain unless explicitly reset

#### Scenario: Unsafe label
- **GIVEN** an element label contains HTML or script
- **WHEN** the diagram renders or exports to Mermaid
- **THEN** the label is escaped and no script executes

### Requirement: Architect annotations
**Requirement ID:** `AT-DIAGRAM_STUDIO-003`

Users MUST annotate boundaries, interface contracts, trust zones, criticality, deployment regions, ownership and confidence.

#### Scenario: Trust boundary
- **GIVEN** an architect marks a public ingress
- **WHEN** an integration design is reviewed
- **THEN** boundary annotation is visible and included in exported architecture documentation

#### Scenario: Annotation permission
- **GIVEN** a viewer tries to add a trust-zone annotation
- **WHEN** the change is submitted
- **THEN** it is rejected and audited

### Requirement: Comparison views
**Requirement ID:** `AT-DIAGRAM_STUDIO-004`

Users MUST compare architecture snapshots and visualize added, removed and modified nodes/edges with source evidence.

#### Scenario: Diagram diff
- **GIVEN** service B changed from REST to Kafka
- **WHEN** two snapshots are compared
- **THEN** relationship type change is highlighted with both evidence sources

#### Scenario: Different environments
- **GIVEN** the user compares a prod snapshot with a dev snapshot
- **WHEN** the comparison opens
- **THEN** the UI warns that environments differ before showing the diff

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

### Requirement: Editorial diagram design system
**Requirement ID:** `AT-DIAGRAM_STUDIO-005`

Every diagram the platform generates or exports MUST use the editorial diagram-design system (adopted from the MIT-licensed diagram-design skill): org-skinnable tokens, node-type treatments, at most two focal accents, and an overview-plus-detail split above nine primary nodes.

#### Scenario: Focal element and budget
- **GIVEN** a C4 container view with 14 containers and one drifted edge
- **WHEN** the platform generates the diagram
- **THEN** it produces an overview with at most nine primary nodes plus linked detail views, and the drifted edge is one of at most two accent-colored focal elements

#### Scenario: Org skin applied
- **GIVEN** an organization has customized its diagram tokens
- **WHEN** a project diagram is exported
- **THEN** the export uses the organization's tokens and never another organization's skin

### Requirement: Diagram conformance linter
**Requirement ID:** `AT-DIAGRAM_STUDIO-006`

Before a diagram is published or exported, a linter MUST verify the design system's connector rules: orthogonal rounded connectors, masked labels with a gap, no overlapping connectors, fanned attach points, no transit behind non-endpoint boxes and no label mask under a later node.

#### Scenario: Linter blocks a broken layout
- **GIVEN** an auto-layout result where two connectors share an attach point and a label overlaps its stroke
- **WHEN** the diagram is exported
- **THEN** the linter reports the violated rules, the layout is re-routed or the export is refused, and no non-conforming diagram is published

#### Scenario: Conforming diagram passes
- **GIVEN** a generated diagram that satisfies every rule
- **WHEN** the linter runs
- **THEN** the export proceeds and the lint result is stored with the diagram version

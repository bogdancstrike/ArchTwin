# Architect-first UX and workspaces

## ADDED Requirements

### Requirement: Project home
**Requirement ID:** `AT-UI_WORKSPACES-001`

The primary UI MUST show project health, latest drift, architecture model, pending decisions, milestones, tasks and source freshness in one contextual home.

#### Scenario: Open project
- **GIVEN** an architect selects project A
- **WHEN** the home opens
- **THEN** all components reflect A and its selected environment

#### Scenario: Project switch clears state
- **GIVEN** the user switches from project A to project B
- **WHEN** the home renders
- **THEN** no cached A widget, title or count is shown under B

### Requirement: Navigation and accessibility
**Requirement ID:** `AT-UI_WORKSPACES-002`

The app MUST support keyboard navigation, responsive layouts, dark/light themes, WCAG 2.2 AA target and clear read-only/preview states.

#### Scenario: Keyboard controls
- **GIVEN** a user navigates diagram panels with keyboard
- **WHEN** they focus an action
- **THEN** its label and action are reachable without a mouse

#### Scenario: Read-only state is explicit
- **GIVEN** a viewer opens an editable diagram
- **WHEN** the editor loads
- **THEN** edit affordances are hidden or disabled and a read-only label is announced to assistive technology

### Requirement: Evidence-first interaction
**Requirement ID:** `AT-UI_WORKSPACES-003`

Users MUST be able to inspect why each inferred entity, drift, AI assertion or proposed edge exists, without leaving its context.

#### Scenario: Inspect graph edge
- **GIVEN** an inferred relation is shown
- **WHEN** the user clicks evidence
- **THEN** the relevant source or trace opens with timestamp and confidence

#### Scenario: Evidence no longer accessible
- **GIVEN** a user lost access to the source behind an edge
- **WHEN** they click evidence
- **THEN** the panel shows that evidence is restricted without revealing its content

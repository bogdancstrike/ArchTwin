# Roadmaps, plans and architecture increments

## ADDED Requirements

### Requirement: Planning hierarchy
**Requirement ID:** `AT-ARCHITECTURE_PLANNING-001`

Each project MUST support strategic goals → capabilities → architecture initiatives → milestones → changes → implementation tasks with ownership and dates.

#### Scenario: Plan to graph
- **GIVEN** initiative introduces a new service
- **WHEN** architect links it to proposed element
- **THEN** planned diagram displays it distinctly from deployed architecture

#### Scenario: Orphan initiative
- **GIVEN** an initiative has no owner
- **WHEN** it is published
- **THEN** publication is refused until an owner is set

### Requirement: Plan evidence
**Requirement ID:** `AT-ARCHITECTURE_PLANNING-002`

Changes MUST link rationale, target design, ADRs, acceptance criteria, dependencies, risks, cost estimates and approval status.

#### Scenario: Unapproved design
- **GIVEN** a change is awaiting review
- **WHEN** a deployment diff appears
- **THEN** product does not claim design was approved

#### Scenario: Approved change
- **GIVEN** a change has its ADR approved
- **WHEN** status renders
- **THEN** approval shows the approver, time and ADR version

### Requirement: Progress projection
**Requirement ID:** `AT-ARCHITECTURE_PLANNING-003`

The platform MUST distinguish externally reported task status from verified architecture implementation state.

#### Scenario: Task closed but no deployment
- **GIVEN** Jira reports Done
- **WHEN** no observed change exists
- **THEN** implementation remains unverified

#### Scenario: Verified implementation
- **GIVEN** Jira reports Done and the expected edge is observed in prod
- **WHEN** progress computes
- **THEN** the change is shown as verified with both evidence links

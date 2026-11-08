# Architecture quality assessments

## ADDED Requirements

### Requirement: Review packs
**Requirement ID:** `AT-ARCHITECTURE_REVIEWS-001`

The platform MUST provide review checklists for reliability, security, scalability, maintainability, data governance and cost with source-backed findings.

#### Scenario: Review service
- **GIVEN** an architect starts reliability review
- **WHEN** checks execute
- **THEN** results distinguish automated evidence from manual assessments

#### Scenario: Missing evidence
- **GIVEN** a reliability check has no connector providing its input
- **WHEN** the review runs
- **THEN** the check is reported as not evaluated instead of passed

### Requirement: Risk register
**Requirement ID:** `AT-ARCHITECTURE_REVIEWS-002`

Architecture risks MUST track severity, likelihood, evidence, owner, mitigation and linked backlog tasks.

#### Scenario: Ownerless critical risk
- **GIVEN** critical SPOF is detected
- **WHEN** review is finalized
- **THEN** it cannot be marked resolved without owner and evidence

#### Scenario: Risk accepted with expiry
- **GIVEN** a risk is accepted by its owner
- **WHEN** the acceptance expiry passes
- **THEN** the risk returns to open and its owner is notified

### Requirement: Recommendations as proposals
**Requirement ID:** `AT-ARCHITECTURE_REVIEWS-003`

Automated architecture recommendations MUST remain proposals requiring human acknowledgment before modifying baselines or generating work items.

#### Scenario: No auto changes
- **GIVEN** AI recommends cache insertion
- **WHEN** suggestion is shown
- **THEN** no architecture baseline is mutated

#### Scenario: Acknowledged recommendation
- **GIVEN** an architect acknowledges a recommendation
- **WHEN** they choose to create a work item
- **THEN** a draft work item is created locally and no remote write happens

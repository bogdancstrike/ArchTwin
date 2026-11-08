# Project federation and cross-platform graph

## ADDED Requirements

### Requirement: Explicit grants
**Requirement ID:** `AT-CROSS_PROJECT_FEDERATION-001`

Cross-project analysis MUST require independently authorized access to every project and an explicit federation grant describing shared relation types and data classes.

#### Scenario: One-sided share
- **GIVEN** project A owner shares to B
- **WHEN** B has not approved bilateral link under policy
- **THEN** federated graph is not exposed

#### Scenario: Grant expiry
- **GIVEN** a federation grant expires
- **WHEN** a federated query runs
- **THEN** only the requesting user's own project data is returned

### Requirement: Boundary-preserving graph
**Requirement ID:** `AT-CROSS_PROJECT_FEDERATION-002`

Federation MUST preserve project ownership, source provenance and independent data retention; it MUST NOT copy sensitive raw artifacts by default.

#### Scenario: Revocation
- **GIVEN** federation grant is removed
- **WHEN** user reopens saved multi-project answer
- **THEN** restricted evidence is re-checked and hidden

#### Scenario: Retention independence
- **GIVEN** project A deletes evidence under its retention policy
- **WHEN** project B views a federated answer
- **THEN** the deleted evidence is not served from B's side

### Requirement: Integration discovery
**Requirement ID:** `AT-CROSS_PROJECT_FEDERATION-003`

The system MUST identify potential integration points from APIs, topics, data contracts and network constraints while reporting missing metadata.

#### Scenario: Two projects
- **GIVEN** architect asks how to link platforms A and B
- **WHEN** analysis runs
- **THEN** candidate interfaces include provenance and unknowns

#### Scenario: No candidates
- **GIVEN** neither project exposes APIs, topics or contracts
- **WHEN** analysis runs
- **THEN** the result states that no integration points were found and lists the missing metadata

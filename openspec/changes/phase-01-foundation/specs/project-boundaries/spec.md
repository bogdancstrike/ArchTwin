# Projects and bounded architecture scope

## ADDED Requirements

### Requirement: Project creation
**Requirement ID:** `AT-PROJECT_BOUNDARIES-001`

A project MUST have a stable ID, organization, title, purpose, system boundaries, owners, tags, environments, repository links, connectors, and data policy.

#### Scenario: Create scoped project
- **GIVEN** an authorized architect supplies required metadata
- **WHEN** the project is created
- **THEN** a distinct project graph and scoped data collection are initialized

#### Scenario: Missing owner
- **GIVEN** a create request omits every owner
- **WHEN** the project is submitted
- **THEN** creation is rejected with a validation error and no partial project rows exist

### Requirement: Project isolation
**Requirement ID:** `AT-PROJECT_BOUNDARIES-002`

Project-scoped reads, diagrams, attachments, search results, LLM context and jobs MUST be constrained to the authorized project before data is retrieved.

#### Scenario: Search leak
- **GIVEN** the user has access to project A only
- **WHEN** search includes a term appearing only in B
- **THEN** no content, counts or titles from B are returned

#### Scenario: Background job scope
- **GIVEN** a scan job for project A is dequeued
- **WHEN** it resolves entities
- **THEN** every query is filtered by project A before execution and a B identifier in the payload is rejected

### Requirement: Cross-project linkage
**Requirement ID:** `AT-PROJECT_BOUNDARIES-003`

Cross-project references MUST require explicit bilateral or organization-policy grants, and MUST preserve ownership and provenance of the source project.

#### Scenario: No implicit federation
- **GIVEN** two projects share a connector
- **WHEN** a user asks for both architectures
- **THEN** access to one MUST NOT imply access to the other

#### Scenario: Grant revocation
- **GIVEN** a federation grant between A and B is revoked
- **WHEN** a cached cross-project view is requested
- **THEN** the cache entry is invalidated and B data is not returned

### Requirement: Environment separation
**Requirement ID:** `AT-PROJECT_BOUNDARIES-004`

Projects MUST distinguish dev/test/staging/prod architectural observations and desired baselines with effective timestamps.

#### Scenario: Production comparison
- **GIVEN** dev and prod have different runtimes
- **WHEN** a user selects prod
- **THEN** only the prod baseline is compared

#### Scenario: Unknown environment
- **GIVEN** a request names an environment not registered for the project
- **WHEN** the architecture endpoint is called
- **THEN** the request fails with not-found instead of falling back to another environment

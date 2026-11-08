# Cross-platform integration design assistant

## ADDED Requirements

### Requirement: Candidate architectures
**Requirement ID:** `AT-INTEGRATION_DESIGNER-001`

The system MUST propose at least two viable integration patterns when evidence allows, such as REST/gRPC, Kafka eventing, file batch, CDC and mediated API gateway.

#### Scenario: A and B
- **GIVEN** two authenticated projects have compatible APIs and an event broker
- **WHEN** architect asks integration options
- **THEN** alternatives include event vs request-based integration with explicit tradeoffs

#### Scenario: Insufficient evidence
- **GIVEN** only one integration style is feasible from the evidence
- **WHEN** options are requested
- **THEN** the assistant explains why alternatives are not viable instead of inventing them

### Requirement: Constraint accounting
**Requirement ID:** `AT-INTEGRATION_DESIGNER-002`

Proposals MUST evaluate contracts, authn/authz, data ownership, latency, consistency, failure modes, retries, idempotency, capacity, network reachability and operational burden.

#### Scenario: Cross-trust boundary
- **GIVEN** projects use separate identity realms
- **WHEN** assistant produces a plan
- **THEN** identity federation and token audience are flagged as design requirements

#### Scenario: Unknown network reachability
- **GIVEN** network zone metadata is missing
- **WHEN** a plan is produced
- **THEN** reachability is listed as an open question, not assumed

### Requirement: Artifacts with approval
**Requirement ID:** `AT-INTEGRATION_DESIGNER-003`

Assistant MUST produce reviewable C4/sequence diagrams, API/event contracts, ADR options and backlog changes without deploying or writing remotely.

#### Scenario: Apply proposal
- **GIVEN** architect accepts one option
- **WHEN** proposal is submitted
- **THEN** new plan artifacts are versioned and remote task write awaits confirmation

#### Scenario: Rejected option
- **GIVEN** the architect rejects all options
- **WHEN** the session closes
- **THEN** no plan artifacts or work items are created

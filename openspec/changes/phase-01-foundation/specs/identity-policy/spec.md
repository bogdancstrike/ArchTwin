# Identity, Cerbos authorization and secrets

## ADDED Requirements

### Requirement: Keycloak authentication
**Requirement ID:** `AT-IDENTITY_POLICY-001`

Interactive users MUST authenticate with Keycloak OIDC Authorization Code + PKCE; APIs MUST validate issuer, audience, lifetime and key rotation.

#### Scenario: Invalid token
- **GIVEN** a token has the wrong audience
- **WHEN** an endpoint is called
- **THEN** the API denies the request before domain access

#### Scenario: Rotated signing key
- **GIVEN** Keycloak rotates its signing key
- **WHEN** a token signed with the new key arrives
- **THEN** the API refreshes JWKS within a bounded interval and accepts the valid token while still rejecting expired ones

### Requirement: Fine-grained authorization
**Requirement ID:** `AT-IDENTITY_POLICY-002`

The system MUST evaluate Cerbos policies for organization, project, environment, diagram, document, ADR, connector, evidence and action types; default deny.

#### Scenario: Unauthorized edit
- **GIVEN** a viewer opens an editable diagram
- **WHEN** the viewer attempts mutation
- **THEN** the command is rejected and audited

#### Scenario: PDP unavailable
- **GIVEN** Cerbos is unreachable
- **WHEN** a protected read or write is requested
- **THEN** the request fails closed with a retriable error and no data is returned

### Requirement: Safe listing
**Requirement ID:** `AT-IDENTITY_POLICY-003`

Collection queries MUST push down verified Cerbos PlanResources predicates when supported, with CheckResources validation on materialized sensitive records; unsupported plans MUST fail closed.

#### Scenario: Policy adapter failure
- **GIVEN** the SQL filter adapter does not understand a plan node
- **WHEN** a list endpoint executes
- **THEN** the request is denied rather than omitting the filter

#### Scenario: Plan pushdown happy path
- **GIVEN** a user may view three of ten diagrams
- **WHEN** the list endpoint runs
- **THEN** exactly three diagrams are returned and total counts exclude the other seven

### Requirement: Credential boundary
**Requirement ID:** `AT-IDENTITY_POLICY-004`

Connector credentials and OAuth tokens MUST be encrypted using envelope encryption with managed rotation, never returned to browsers, model prompts or logs.

#### Scenario: Credential inspection
- **GIVEN** a user is permitted to edit a connector
- **WHEN** they GET the connector
- **THEN** secrets are redacted and stored only server-side

#### Scenario: Secret canary
- **GIVEN** a canary token is stored as a connector secret
- **WHEN** logs, traces, API responses and exports are scanned after a full sync
- **THEN** the canary value appears nowhere

### Requirement: Agent permissions
**Requirement ID:** `AT-IDENTITY_POLICY-005`

AI retrieval and tool executions MUST run under the initiating user and project authorization context without assuming platform-wide service privileges.

#### Scenario: Prompt injection
- **GIVEN** external source text instructs the assistant to read another project
- **WHEN** the instruction is processed
- **THEN** policy denies cross-project access and logs the attempt

#### Scenario: Permission revoked mid-run
- **GIVEN** a user loses project access while an AI request is running
- **WHEN** the next retrieval tool call executes
- **THEN** the call is denied under the current entitlements and the run stops with an authorization error

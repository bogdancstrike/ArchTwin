# Secure connector lifecycle and ingestion SDK

## ADDED Requirements

### Requirement: Connector types
**Requirement ID:** `AT-CONNECTOR_PLATFORM-001`

Connectors MUST be versioned adapters with declared capabilities, auth, scopes, rate limits, webhooks/pollers, sync cursors, health and mapping contracts.

#### Scenario: Test connection
- **GIVEN** a user provides GitLab access
- **WHEN** they test the connector
- **THEN** permissions and accessible projects are displayed without exposing the token

#### Scenario: Over-privileged token warning
- **GIVEN** the supplied token has write scopes
- **WHEN** the connector is tested
- **THEN** the UI shows the excess scopes and the organization policy can block activation

### Requirement: Safe execution
**Requirement ID:** `AT-CONNECTOR_PLATFORM-002`

Connector access MUST use least-privilege credentials, outbound allowlists, SSRF protections, per-project quotas, circuit breakers and bounded retries.

#### Scenario: SSRF
- **GIVEN** a user registers a connector pointing at link-local metadata IP
- **WHEN** connection test runs
- **THEN** connection is blocked and audited

#### Scenario: Redirect to private address
- **GIVEN** an allowed host redirects to 10.0.0.5
- **WHEN** the connector follows the redirect
- **THEN** the request is blocked after re-resolution and audited

### Requirement: Resynchronization
**Requirement ID:** `AT-CONNECTOR_PLATFORM-003`

Connectors MUST handle initial full scans, incremental updates, deletion tombstones, reconciliation and provider rate limits without duplicating entities.

#### Scenario: Webhook lost
- **GIVEN** a provider event is missed
- **WHEN** nightly reconciliation runs
- **THEN** the source inventory converges and marks last-seen information

#### Scenario: Partial scan is not deletion
- **GIVEN** a full scan stops at page 7 of 10 because of a rate limit
- **WHEN** reconciliation finishes
- **THEN** entities on unseen pages are kept as stale, not tombstoned

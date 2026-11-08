# Near-real-time watchers and reconciliation

## ADDED Requirements

### Requirement: Event-first ingestion
**Requirement ID:** `AT-CONTINUOUS_WATCHERS-001`

Webhook/watch sources MUST trigger bounded incremental scans within the configured target interval; polling and periodic full reconciliation MUST handle missed events.

#### Scenario: Git push
- **GIVEN** a webhook arrives for repo commit
- **WHEN** processing is available
- **THEN** the related project graph is refreshed within the configured target interval

#### Scenario: Webhooks disabled
- **GIVEN** connectors.webhooks is off
- **WHEN** a provider sends a webhook
- **THEN** the event is rejected and polling continues at the configured interval

### Requirement: Backpressure and ordering
**Requirement ID:** `AT-CONTINUOUS_WATCHERS-002`

Watchers MUST deduplicate provider events, checkpoint cursors, bound queue sizes, handle out-of-order delivery and enforce per-project quotas.

#### Scenario: Burst
- **GIVEN** 10k events arrive for one repository
- **WHEN** queues process
- **THEN** coalescing avoids redundant full scans and no other tenant starves

#### Scenario: Out-of-order events
- **GIVEN** an event for commit B arrives before commit A, which is its parent
- **WHEN** both are processed
- **THEN** the final snapshot reflects commit B

### Requirement: Failure behavior
**Requirement ID:** `AT-CONTINUOUS_WATCHERS-003`

Failed connectors MUST expose degraded state, preserve last known architecture and never mark unverifiable elements deleted.

#### Scenario: K8s unreachable
- **GIVEN** watcher loses cluster connection
- **WHEN** evaluation runs
- **THEN** last-known data is marked stale and no false deletion drift is emitted

#### Scenario: Recovery after outage
- **GIVEN** the cluster connection returns after an outage
- **WHEN** the watcher resumes
- **THEN** a full reconcile runs before deletion drift can be emitted

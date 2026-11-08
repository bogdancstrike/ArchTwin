# Architecture alerts and digests

## ADDED Requirements

### Requirement: Notification routing
**Requirement ID:** `AT-ARCHITECTURE_NOTIFICATIONS-001`

The system MUST deliver project-scoped alerts through in-app notifications, email and configurable webhooks, with deduplication and severity routes.

#### Scenario: No duplicate flood
- **GIVEN** five matching events arrive
- **WHEN** alert engine processes
- **THEN** one deduplicated incident is delivered with an occurrence count

#### Scenario: Failed webhook delivery
- **GIVEN** a webhook endpoint returns 500
- **WHEN** delivery retries reach the limit
- **THEN** the delivery is dead-lettered and visible to the project owner

### Requirement: Policies
**Requirement ID:** `AT-ARCHITECTURE_NOTIFICATIONS-002`

Users MUST configure quiet hours, thresholds, escalation, severity routing and delivery retries without allowing alerts to bypass authorization.

#### Scenario: Restricted alert
- **GIVEN** an event concerns secret architecture
- **WHEN** viewer receives email
- **THEN** restricted titles and fields are not disclosed

#### Scenario: Quiet hours
- **GIVEN** quiet hours are active and a medium-severity alert fires
- **WHEN** routing evaluates
- **THEN** it is queued for the digest while critical alerts still go through

### Requirement: SLO monitoring
**Requirement ID:** `AT-ARCHITECTURE_NOTIFICATIONS-003`

Drift monitoring MUST record detection latency, scan lag, connector health and false-positive rate as measurable platform KPIs.

#### Scenario: Lag
- **GIVEN** Kubernetes watcher is stalled
- **WHEN** dashboard displays health
- **THEN** scan-lag breach is visible

#### Scenario: False-positive rate
- **GIVEN** users mark findings as false positives
- **WHEN** the KPI computes
- **THEN** the false-positive rate per rule is shown and breaches of the target alert operators

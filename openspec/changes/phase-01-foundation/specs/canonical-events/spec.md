# Persistent data model and domain events

## ADDED Requirements

### Requirement: Transaction consistency
**Requirement ID:** `AT-CANONICAL_EVENTS-001`

The system MUST use PostgreSQL transactions and an outbox for mutations that publish domain events; consumers MUST be idempotent.

#### Scenario: Commit failure
- **GIVEN** a project update rolls back
- **WHEN** the outbox publisher runs
- **THEN** no project-updated event is delivered

#### Scenario: Consumer crash after delivery
- **GIVEN** a consumer processes an event and crashes before acknowledging
- **WHEN** the event is redelivered
- **THEN** the side effect is applied exactly once

### Requirement: Stable global identifiers
**Requirement ID:** `AT-CANONICAL_EVENTS-002`

All entities MUST use opaque stable IDs and carry organization_id and project_id where applicable; upserts MUST be idempotent on provider key and source identity.

#### Scenario: Repeat discovery
- **GIVEN** a Git webhook is delivered twice
- **WHEN** ingestion processes both deliveries
- **THEN** only one effective inventory version is created

#### Scenario: Older revision arrives late
- **GIVEN** revision 5 of a resource is stored
- **WHEN** revision 4 is delivered afterwards
- **THEN** canonical state stays at revision 5 and revision 4 is kept only as history

### Requirement: Versioned snapshots
**Requirement ID:** `AT-CANONICAL_EVENTS-003`

The canonical architecture snapshot MUST be immutable, queryable by effective time, and comparable to other snapshots.

#### Scenario: Historical view
- **GIVEN** today differs from yesterday
- **WHEN** an architect opens yesterday
- **THEN** the previous view remains reproducible

#### Scenario: Snapshot immutability
- **GIVEN** a snapshot has been published
- **WHEN** any process attempts to update its rows
- **THEN** the database rejects the update

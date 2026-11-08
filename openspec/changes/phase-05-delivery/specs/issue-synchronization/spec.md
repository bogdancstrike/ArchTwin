# Taiga, Jira, GitLab and GitHub work tracking

## ADDED Requirements

### Requirement: Issue ingestion
**Requirement ID:** `AT-ISSUE_SYNCHRONIZATION-001`

When enabled, Jira, Taiga, GitLab and GitHub connectors MUST support initial sync, webhooks where available, fallback polling and status mappings.

#### Scenario: Provider disabled
- **GIVEN** Taiga flag turns off
- **WHEN** a queued Taiga sync reaches worker
- **THEN** the worker exits without contacting Taiga

#### Scenario: Unmapped status
- **GIVEN** a provider introduces a new status value
- **WHEN** sync runs
- **THEN** the item is stored with the raw status and flagged unmapped instead of guessing

### Requirement: Linking and conflicts
**Requirement ID:** `AT-ISSUE_SYNCHRONIZATION-002`

Work items MUST support explicit mappings to architecture changes, ADRs, nodes and milestones; synchronization MUST record conflict and source-of-truth rules.

#### Scenario: Concurrent change
- **GIVEN** title changes locally and in Jira
- **WHEN** sync detects conflict
- **THEN** a conflict is surfaced instead of last-writer-wins deletion

#### Scenario: AI suggestions are not links
- **GIVEN** the assistant suggests linking an issue to an ADR
- **WHEN** the suggestion is shown
- **THEN** no link exists until a user confirms it

### Requirement: Controlled write-back
**Requirement ID:** `AT-ISSUE_SYNCHRONIZATION-003`

External task creation and updates MUST be independently flagged, permission checked, previewed, and explicitly confirmed with idempotency keys.

#### Scenario: AI tasks
- **GIVEN** assistant drafts a task list
- **WHEN** user clicks Preview
- **THEN** no remote issue is written until Apply and authorization succeed

#### Scenario: Duplicate apply
- **GIVEN** the user clicks Apply twice
- **WHEN** both requests reach the server
- **THEN** the same idempotency key yields one remote issue

# GitHub/GitLab, Jira and Taiga application connectors

## ADDED Requirements

### Requirement: Work connector support
**Requirement ID:** `AT-WORK_CONNECTORS-001`

GitHub Issues/PRs, GitLab Issues/MRs, Jira issues and Taiga tasks/user stories MUST be adapters using documented provider APIs and scoped OAuth/PAT as applicable.

#### Scenario: Taiga opt-in
- **GIVEN** Taiga feature flag is disabled
- **WHEN** an admin opens connectors
- **THEN** Taiga cannot sync or start webhook registration

#### Scenario: Invalid webhook signature
- **GIVEN** a Jira webhook arrives with a wrong signature
- **WHEN** ingress verifies it
- **THEN** the event is rejected, nothing is stored and the attempt is metered

### Requirement: Change ingestion
**Requirement ID:** `AT-WORK_CONNECTORS-002`

External issue events MUST be linked to canonical work items while preserving provider IDs, URLs, status, assignment, timestamps, and version provenance.

#### Scenario: Issue reopened
- **GIVEN** Jira reopens a closed task
- **WHEN** sync runs
- **THEN** local status changes with clear external provenance

#### Scenario: Deleted remote issue
- **GIVEN** an issue is deleted in GitHub
- **WHEN** the next reconcile runs
- **THEN** the local work item is tombstoned with provenance and its links remain historically visible

### Requirement: Read-only first
**Requirement ID:** `AT-WORK_CONNECTORS-003`

All external work-tracker connectors MUST be read-only initially; optional write-back MUST require an independently enabled flag and explicit user confirmation.

#### Scenario: No silent issue creation
- **GIVEN** AI suggests three tasks
- **WHEN** an architect reviews the suggestion
- **THEN** no issue is created before approval

#### Scenario: Write scope absent
- **GIVEN** the connector token has no write scope
- **WHEN** a user tries to enable write-back
- **THEN** enablement is refused with an explanation

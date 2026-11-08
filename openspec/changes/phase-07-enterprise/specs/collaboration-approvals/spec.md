# Multi-user collaboration, comments and approvals

## ADDED Requirements

### Requirement: Workspace collaboration
**Requirement ID:** `AT-COLLABORATION_APPROVALS-001`

Authorized project members MUST collaborate on architecture reviews, diagrams, docs and plans with comments, mentions and review assignments.

#### Scenario: Concurrent edits
- **GIVEN** two architects edit a document
- **WHEN** one commits after the other
- **THEN** conflicts are surfaced with version compare, not silently overwritten

#### Scenario: Mention outside project
- **GIVEN** a user mentions someone who is not a project member
- **WHEN** the comment is saved
- **THEN** no notification or content is sent to that person

### Requirement: Approval controls
**Requirement ID:** `AT-COLLABORATION_APPROVALS-002`

Approved architecture baselines, ADRs and high-risk cross-project links MUST require configurable approvers and separation of duties.

#### Scenario: High-risk decision
- **GIVEN** author attempts to self-approve
- **WHEN** policy requires independent sign-off
- **THEN** the transition is rejected

#### Scenario: Approver loses role
- **GIVEN** an assigned approver loses the approver role
- **WHEN** they try to approve
- **THEN** the approval is denied

### Requirement: Notifications and access
**Requirement ID:** `AT-COLLABORATION_APPROVALS-003`

Shared links and notifications MUST recheck authorization at access time and MUST not embed secret architecture details in push bodies.

#### Scenario: Revoked access
- **GIVEN** user loses project membership
- **WHEN** old notification link is opened
- **THEN** access is denied

#### Scenario: Push body minimal
- **GIVEN** a drift alert is sent to Slack
- **WHEN** the message is built
- **THEN** it contains only a link and a non-sensitive summary

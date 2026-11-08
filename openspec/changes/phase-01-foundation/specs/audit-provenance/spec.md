# Auditability and evidence provenance

## ADDED Requirements

### Requirement: Audit envelope
**Requirement ID:** `AT-AUDIT_PROVENANCE-001`

All security-relevant and architecture-changing actions MUST record actor, organization, project, time, action, target, result, trace ID, policy decision ID and before/after reference.

#### Scenario: ADR approval
- **GIVEN** an architect approves an ADR
- **WHEN** the approval commits
- **THEN** an immutable audit event links approval and document version

#### Scenario: Denied action is audited
- **GIVEN** a viewer attempts to approve an ADR
- **WHEN** the policy denies it
- **THEN** an audit event records the denial with the policy decision ID

### Requirement: Evidence references
**Requirement ID:** `AT-AUDIT_PROVENANCE-002`

Facts, relationships and AI outputs MUST reference source identifiers, observed_at, collected_at, parser version, confidence and immutable snapshot hash where applicable.

#### Scenario: Outdated source
- **GIVEN** a diagram edge is based on an older snapshot
- **WHEN** a new source disagrees
- **THEN** the old edge stays historically inspectable with stale status

#### Scenario: Fact without source
- **GIVEN** a normalizer emits a fact without a source identifier
- **WHEN** the write is attempted
- **THEN** the record is rejected and the normalizer error is reported

### Requirement: Tamper evidence
**Requirement ID:** `AT-AUDIT_PROVENANCE-003`

Audit exports MUST support ordered integrity digests and chain verification; export verification MUST fail if an event has been altered.

#### Scenario: Tampered export
- **GIVEN** a byte in an exported event is modified
- **WHEN** integrity verification runs
- **THEN** verification reports failure

#### Scenario: Deleted event detected
- **GIVEN** an event is removed from the middle of an exported chain
- **WHEN** verification runs
- **THEN** verification reports the gap and the position of the missing event

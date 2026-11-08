# Organizations and governance

## ADDED Requirements

### Requirement: Organization tenancy
**Requirement ID:** `AT-ORGANIZATIONS-001`

The system MUST isolate organizations by immutable organization_id in every persisted domain row and object-storage prefix and MUST reject cross-organization identifiers by default.

#### Scenario: Cross-tenant lookup
- **GIVEN** a user belongs only to organization A
- **WHEN** the user requests a project identifier from B
- **THEN** the response is not found or forbidden without leaking metadata

#### Scenario: Client-supplied tenant ignored
- **GIVEN** a request body or header carries organization_id of B
- **WHEN** user A creates a project
- **THEN** the server derives the organization from the verified principal and rejects or ignores the mismatched value

### Requirement: Organization lifecycle
**Requirement ID:** `AT-ORGANIZATIONS-002`

The system MUST support organization settings, approved administrators, retention policy and export/deletion workflows with an auditable approval step.

#### Scenario: Controlled deletion
- **GIVEN** an administrator requests deletion with active projects
- **WHEN** the request is submitted
- **THEN** an approval workflow and retention checks run before destructive execution

#### Scenario: Deletion without approval
- **GIVEN** an administrator calls the deletion endpoint without a completed approval
- **WHEN** the command executes
- **THEN** no data is deleted and the attempt is audited as denied

### Requirement: Ownership
**Requirement ID:** `AT-ORGANIZATIONS-003`

Each organization MUST retain at least one active owner and MUST define break-glass procedures with time limits and audit records.

#### Scenario: Last owner
- **GIVEN** one active organization owner remains
- **WHEN** their role is removed
- **THEN** the operation is denied

#### Scenario: Break-glass expiry
- **GIVEN** a break-glass grant was issued for 60 minutes
- **WHEN** the operator acts after expiry
- **THEN** access is denied and both grant and denial appear in the audit log

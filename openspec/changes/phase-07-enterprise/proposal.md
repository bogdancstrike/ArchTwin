# Proposal: Enterprise operations and extensibility

## Why
ArchTwin is a greenfield, architect-first system. This change establishes a bounded, verifiable delivery increment, not a claim that functionality has already been implemented. Its capability deltas are the feature contracts for this increment.

## What Changes
- Add **Reliability, scale, backup and retention** (`enterprise-operations`).
- Add **Multi-user collaboration, comments and approvals** (`collaboration-approvals`).
- Add **Unified search, discovery and portability** (`unified-search-export`).
- Add **Extension SDK and connector marketplace model** (`connector-sdk`).
- Add **Architecture health and portfolio insights** (`architecture-health`).

## Dependencies
Harden phases 01–06 after measured pilot feedback.

## Rollout and rollback
- Feature flags for every module default OFF until its contract, permissions and tests pass. Foundation identity/auth/audit never bypassed by flag.
- Introduce read-only integrations before write-back. Backfill and migration jobs are resumable and idempotent.
- Rollback disables the affected module or connector, drains queued work, restores previous read paths, and preserves audit and immutable history.
- No external infrastructure mutation occurs as part of this change without a separate approved action.

## Success
- Each requirement's scenario has executable tests and linked code or integration evidence.
- Feature flags, authorization, provenance and negative-path tests pass before a module is enabled.
- A demo project can exercise the phase's end-to-end journey described in `docs/acceptance/end-to-end-journeys.md`.

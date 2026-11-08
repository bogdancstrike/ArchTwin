# Proposal: Continuous drift and early-warning intelligence

## Why
ArchTwin is a greenfield, architect-first system. This change establishes a bounded, verifiable delivery increment, not a claim that functionality has already been implemented. Its capability deltas are the feature contracts for this increment.

## What Changes
- Add **Desired, observed and implemented architecture drift** (`drift-engine`).
- Add **Near-real-time watchers and reconciliation** (`continuous-watchers`).
- Add **Drift scoring and lifecycle** (`drift-triage`).
- Add **Architecture alerts and digests** (`architecture-notifications`).

## Dependencies
Complete phases 01–03, with sources and baseline snapshots.

## Rollout and rollback
- Feature flags for every module default OFF until its contract, permissions and tests pass. Foundation identity/auth/audit never bypassed by flag.
- Introduce read-only integrations before write-back. Backfill and migration jobs are resumable and idempotent.
- Rollback disables the affected module or connector, drains queued work, restores previous read paths, and preserves audit and immutable history.
- No external infrastructure mutation occurs as part of this change without a separate approved action.

## Success
- Each requirement's scenario has executable tests and linked code or integration evidence.
- Feature flags, authorization, provenance and negative-path tests pass before a module is enabled.
- A demo project can exercise the phase's end-to-end journey described in `docs/acceptance/end-to-end-journeys.md`.

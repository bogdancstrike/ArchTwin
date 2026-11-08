# Proposal: Grounded AI and cross-platform design

## Why
ArchTwin is a greenfield, architect-first system. This change establishes a bounded, verifiable delivery increment, not a claim that functionality has already been implemented. Its capability deltas are the feature contracts for this increment.

## What Changes
- Add **Grounded AI architecture copilot** (`architecture-assistant`).
- Add **Project federation and cross-platform graph** (`cross-project-federation`).
- Add **Cross-platform integration design assistant** (`integration-designer`).
- Add **What-if simulation and blast-radius analysis** (`impact-analysis`).
- Add **AI quality, security and model flexibility** (`ai-evaluations`).

## Dependencies
Complete phases 01–03; usable with minimal evidence first.

## Rollout and rollback
- Feature flags for every module default OFF until its contract, permissions and tests pass. Foundation identity/auth/audit never bypassed by flag.
- Introduce read-only integrations before write-back. Backfill and migration jobs are resumable and idempotent.
- Rollback disables the affected module or connector, drains queued work, restores previous read paths, and preserves audit and immutable history.
- No external infrastructure mutation occurs as part of this change without a separate approved action.

## Success
- Each requirement's scenario has executable tests and linked code or integration evidence.
- Feature flags, authorization, provenance and negative-path tests pass before a module is enabled.
- A demo project can exercise the phase's end-to-end journey described in `docs/acceptance/end-to-end-journeys.md`.

# ADR-0006: Connectors read-only by default; write-back only with approval

- **Status:** Accepted (planning baseline)
- **Date:** 2026-11-08

## Context and problem
Customers will not grant write access to repos, clusters or trackers to a new tool, and AI-initiated writes are a major risk.

## Decision
Connectors request read-only scopes and warn about excess privileges. External writes (issues, PRs) require a per-provider flag, Cerbos `write_external`, a preview, explicit user approval, an idempotency key and audit. No connector ever mutates infrastructure.

## Alternatives considered
- Bidirectional sync by default — rejected: trust and blast radius.

## Consequences
- Lower onboarding friction and risk.
- Some workflows stay manual until write-back is enabled per project.

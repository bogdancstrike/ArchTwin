# ADR-0008: OpenFeature flags with a PostgreSQL provider; core is not flaggable

- **Status:** Accepted (planning baseline)
- **Date:** 2026-11-08

## Context and problem
Every optional module/provider/AI operation needs a kill switch with org/project scoping and audit, without vendor lock-in.

## Decision
Flags are declared in a typed catalog (generated from `docs/feature-flags/FLAG_CATALOG.md`), overridden in PostgreSQL, and evaluated through the **OpenFeature** API with a custom provider; invalidation via `LISTEN/NOTIFY`. Core modules and security invariants are never flags.

## Alternatives considered
- Unleash/flagd now — possible later behind the same OpenFeature API.
- Homegrown flag API — rejected: lock-in to our own interface.

## Consequences
- Queued jobs re-check flags at execution.
- Stale cache for high-risk actions ⇒ treated as disabled.

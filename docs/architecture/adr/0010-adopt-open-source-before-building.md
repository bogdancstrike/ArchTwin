# ADR-0010: Adopt open source before building

- **Status:** Accepted (planning baseline)
- **Date:** 2026-11-08

## Context and problem
Scope is large and the team small; infrastructure built in-house competes with product work and carries security risk.

## Decision
Prefer foundation-backed or widely adopted OSS (see `docs/TECHNOLOGIES.md`) behind small interfaces. Custom infrastructure code requires an ADR showing why no adopted component fits. Track licences in `THIRD_PARTY_NOTICES.md`; Renovate keeps dependencies current.

## Alternatives considered
- Build for full control — rejected for non-differentiating concerns.

## Consequences
- Faster delivery and fewer security bugs.
- Dependency and licence monitoring becomes a standing task.

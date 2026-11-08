# ADR-0007: Temporal for all durable work

- **Status:** Accepted (planning baseline)
- **Date:** 2026-11-08

## Context and problem
Scans, reconciliation, digests, approvals and deletions are long-running, need retries, timers and human waits.

## Decision
Use **Temporal** (same PostgreSQL in dev) for every durable job and schedule; activities re-check feature flags and entitlements before acting. The outbox relay hands events to Temporal workflows.

## Alternatives considered
- Celery/arq + cron — rejected: retries/timers/visibility must be rebuilt.
- Kafka Streams — rejected: no broker in MVP.

## Consequences
- One mental model for background work, proven in Horizon.
- Temporal is an additional service to operate (single container in dev).

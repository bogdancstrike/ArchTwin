# ADR-0003: Three-way evidence model with UNKNOWN semantics

- **Status:** Accepted (planning baseline)
- **Date:** 2026-11-08

## Context and problem
Drift and AI answers are only trustworthy if intent, code and runtime facts are never conflated and missing data is not treated as absence.

## Decision
Every fact is an immutable observation with origin (`desired`, `static`, `runtime`, `planned`, `issue`, `inferred`, `manual`), source revision, observed_at, parser/mapping version and confidence. Connectors declare freshness SLAs and coverage; stale or partial coverage yields `unknown`/`incomplete`, never `missing`. Drift is computed by **deterministic, versioned rules** over immutable snapshots; LLMs may explain, never detect.

## Alternatives considered
- Single merged 'truth' graph — rejected: loses provenance, causes false drift.
- LLM-based drift detection — rejected: non-reproducible, untestable.

## Consequences
- Findings are reproducible and explainable.
- More storage (append-only observations, partitioned by month).
- UI must always show origin, freshness and confidence.

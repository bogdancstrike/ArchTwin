# ADR-0001: Modular monolith first

- **Status:** Accepted (planning baseline)
- **Date:** 2026-11-08

## Context and problem
ArchTwin is built by a very small team, needs strong transactional consistency between authorization, audit, evidence and outbox, and has unproven load.

## Decision
One FastAPI API process and Temporal workers built from the **same image**, organized as bounded Python packages (`orgs`, `projects`, `iam`, `connectors`, `inventory`, `architecture`, `drift`, …) that communicate via service interfaces and domain events, never via each other's tables. Separate processes only for isolation needs (Docling, renderers, sandboxed code analysis, plugins).

## Alternatives considered
- Microservices per domain — rejected: distributed transactions, ops cost, no measured need.
- Serverless functions — rejected: long scans and human waits fit Temporal better.

## Consequences
- Simple deploys, one migration stream, easy refactoring.
- Module boundaries must be enforced by review and import-linter rules.
- A module can be extracted later if an ADR shows measured need.

# Implementation tasks

Change: **phase-05-delivery**. All items start unchecked. Trace them to code and test evidence.

## Domain implementation
- [ ] 1.1 Define data contracts, permissions, idempotency and API surface for **architecture-planning**.
- [ ] 1.2 Implement the vertical slice for **architecture-planning** behind flag `architecture_planning` or its catalog-defined equivalent.
- [ ] 1.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **architecture-planning**.
- [ ] 1.4 Add feature/operator documentation, metrics, and a rollback exercise for **architecture-planning**.
- [ ] 2.1 Define data contracts, permissions, idempotency and API surface for **issue-synchronization**.
- [ ] 2.2 Implement the vertical slice for **issue-synchronization** behind flag `issue_synchronization` or its catalog-defined equivalent.
- [ ] 2.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **issue-synchronization**.
- [ ] 2.4 Add feature/operator documentation, metrics, and a rollback exercise for **issue-synchronization**.
- [ ] 3.1 Define data contracts, permissions, idempotency and API surface for **implementation-traceability**.
- [ ] 3.2 Implement the vertical slice for **implementation-traceability** behind flag `implementation_traceability` or its catalog-defined equivalent.
- [ ] 3.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **implementation-traceability**.
- [ ] 3.4 Add feature/operator documentation, metrics, and a rollback exercise for **implementation-traceability**.
- [ ] 4.1 Define data contracts, permissions, idempotency and API surface for **release-gates**.
- [ ] 4.2 Implement the vertical slice for **release-gates** behind flag `release_gates` or its catalog-defined equivalent.
- [ ] 4.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **release-gates**.
- [ ] 4.4 Add feature/operator documentation, metrics, and a rollback exercise for **release-gates**.

## Phase exit gates
- [ ] X.1 Review security and threats; verify default-deny policies and data minimization.
- [ ] X.2 Measure latency, budgets, and freshness against the phase-specific SLOs.
- [ ] X.3 Demonstrate project A/B isolation, auditability and reproducible evidence.
- [ ] X.4 Enable for a pilot project only; confirm rollback works.

# Implementation tasks

Change: **phase-04-drift**. All items start unchecked. Trace them to code and test evidence.

## Domain implementation
- [ ] 1.1 Define data contracts, permissions, idempotency and API surface for **drift-engine**.
- [ ] 1.2 Implement the vertical slice for **drift-engine** behind flag `drift_engine` or its catalog-defined equivalent.
- [ ] 1.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **drift-engine**.
- [ ] 1.4 Add feature/operator documentation, metrics, and a rollback exercise for **drift-engine**.
- [ ] 2.1 Define data contracts, permissions, idempotency and API surface for **continuous-watchers**.
- [ ] 2.2 Implement the vertical slice for **continuous-watchers** behind flag `continuous_watchers` or its catalog-defined equivalent.
- [ ] 2.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **continuous-watchers**.
- [ ] 2.4 Add feature/operator documentation, metrics, and a rollback exercise for **continuous-watchers**.
- [ ] 3.1 Define data contracts, permissions, idempotency and API surface for **drift-triage**.
- [ ] 3.2 Implement the vertical slice for **drift-triage** behind flag `drift_triage` or its catalog-defined equivalent.
- [ ] 3.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **drift-triage**.
- [ ] 3.4 Add feature/operator documentation, metrics, and a rollback exercise for **drift-triage**.
- [ ] 4.1 Define data contracts, permissions, idempotency and API surface for **architecture-notifications**.
- [ ] 4.2 Implement the vertical slice for **architecture-notifications** behind flag `architecture_notifications` or its catalog-defined equivalent.
- [ ] 4.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **architecture-notifications**.
- [ ] 4.4 Add feature/operator documentation, metrics, and a rollback exercise for **architecture-notifications**.

## Phase exit gates
- [ ] X.1 Review security and threats; verify default-deny policies and data minimization.
- [ ] X.2 Measure latency, budgets, and freshness against the phase-specific SLOs.
- [ ] X.3 Demonstrate project A/B isolation, auditability and reproducible evidence.
- [ ] X.4 Enable for a pilot project only; confirm rollback works.

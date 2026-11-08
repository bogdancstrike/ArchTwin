# Implementation tasks

Change: **phase-07-enterprise**. All items start unchecked. Trace them to code and test evidence.

## Domain implementation
- [ ] 1.1 Define data contracts, permissions, idempotency and API surface for **enterprise-operations**.
- [ ] 1.2 Implement the vertical slice for **enterprise-operations** behind flag `enterprise_operations` or its catalog-defined equivalent.
- [ ] 1.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **enterprise-operations**.
- [ ] 1.4 Add feature/operator documentation, metrics, and a rollback exercise for **enterprise-operations**.
- [ ] 2.1 Define data contracts, permissions, idempotency and API surface for **collaboration-approvals**.
- [ ] 2.2 Implement the vertical slice for **collaboration-approvals** behind flag `collaboration_approvals` or its catalog-defined equivalent.
- [ ] 2.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **collaboration-approvals**.
- [ ] 2.4 Add feature/operator documentation, metrics, and a rollback exercise for **collaboration-approvals**.
- [ ] 3.1 Define data contracts, permissions, idempotency and API surface for **unified-search-export**.
- [ ] 3.2 Implement the vertical slice for **unified-search-export** behind flag `unified_search_export` or its catalog-defined equivalent.
- [ ] 3.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **unified-search-export**.
- [ ] 3.4 Add feature/operator documentation, metrics, and a rollback exercise for **unified-search-export**.
- [ ] 4.1 Define data contracts, permissions, idempotency and API surface for **connector-sdk**.
- [ ] 4.2 Implement the vertical slice for **connector-sdk** behind flag `connector_sdk` or its catalog-defined equivalent.
- [ ] 4.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **connector-sdk**.
- [ ] 4.4 Add feature/operator documentation, metrics, and a rollback exercise for **connector-sdk**.
- [ ] 5.1 Define data contracts, permissions, idempotency and API surface for **architecture-health**.
- [ ] 5.2 Implement the vertical slice for **architecture-health** behind flag `architecture_health` or its catalog-defined equivalent.
- [ ] 5.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **architecture-health**.
- [ ] 5.4 Add feature/operator documentation, metrics, and a rollback exercise for **architecture-health**.

## Phase exit gates
- [ ] X.1 Review security and threats; verify default-deny policies and data minimization.
- [ ] X.2 Measure latency, budgets, and freshness against the phase-specific SLOs.
- [ ] X.3 Demonstrate project A/B isolation, auditability and reproducible evidence.
- [ ] X.4 Enable for a pilot project only; confirm rollback works.

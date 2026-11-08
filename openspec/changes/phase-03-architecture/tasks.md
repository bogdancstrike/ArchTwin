# Implementation tasks

Change: **phase-03-architecture**. All items start unchecked. Trace them to code and test evidence.

## Domain implementation
- [ ] 1.1 Define data contracts, permissions, idempotency and API surface for **architecture-graph**.
- [ ] 1.2 Implement the vertical slice for **architecture-graph** behind flag `architecture_graph` or its catalog-defined equivalent.
- [ ] 1.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **architecture-graph**.
- [ ] 1.4 Add feature/operator documentation, metrics, and a rollback exercise for **architecture-graph**.
- [ ] 2.1 Define data contracts, permissions, idempotency and API surface for **diagram-studio**.
- [ ] 2.2 Implement the vertical slice for **diagram-studio** behind flag `diagram_studio` or its catalog-defined equivalent.
- [ ] 2.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **diagram-studio**.
- [ ] 2.4 Add feature/operator documentation, metrics, and a rollback exercise for **diagram-studio**.
- [ ] 3.1 Define data contracts, permissions, idempotency and API surface for **documentation-engine**.
- [ ] 3.2 Implement the vertical slice for **documentation-engine** behind flag `documentation_engine` or its catalog-defined equivalent.
- [ ] 3.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **documentation-engine**.
- [ ] 3.4 Add feature/operator documentation, metrics, and a rollback exercise for **documentation-engine**.
- [ ] 4.1 Define data contracts, permissions, idempotency and API surface for **adr-workflow**.
- [ ] 4.2 Implement the vertical slice for **adr-workflow** behind flag `adr_workflow` or its catalog-defined equivalent.
- [ ] 4.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **adr-workflow**.
- [ ] 4.4 Add feature/operator documentation, metrics, and a rollback exercise for **adr-workflow**.
- [ ] 5.1 Define data contracts, permissions, idempotency and API surface for **architecture-reviews**.
- [ ] 5.2 Implement the vertical slice for **architecture-reviews** behind flag `architecture_reviews` or its catalog-defined equivalent.
- [ ] 5.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **architecture-reviews**.
- [ ] 5.4 Add feature/operator documentation, metrics, and a rollback exercise for **architecture-reviews**.

## Phase exit gates
- [ ] X.1 Review security and threats; verify default-deny policies and data minimization.
- [ ] X.2 Measure latency, budgets, and freshness against the phase-specific SLOs.
- [ ] X.3 Demonstrate project A/B isolation, auditability and reproducible evidence.
- [ ] X.4 Enable for a pilot project only; confirm rollback works.

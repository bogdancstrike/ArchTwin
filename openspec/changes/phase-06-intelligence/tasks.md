# Implementation tasks

Change: **phase-06-intelligence**. All items start unchecked. Trace them to code and test evidence.

## Domain implementation
- [ ] 1.1 Define data contracts, permissions, idempotency and API surface for **architecture-assistant**.
- [ ] 1.2 Implement the vertical slice for **architecture-assistant** behind flag `architecture_assistant` or its catalog-defined equivalent.
- [ ] 1.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **architecture-assistant**.
- [ ] 1.4 Add feature/operator documentation, metrics, and a rollback exercise for **architecture-assistant**.
- [ ] 2.1 Define data contracts, permissions, idempotency and API surface for **cross-project-federation**.
- [ ] 2.2 Implement the vertical slice for **cross-project-federation** behind flag `cross_project_federation` or its catalog-defined equivalent.
- [ ] 2.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **cross-project-federation**.
- [ ] 2.4 Add feature/operator documentation, metrics, and a rollback exercise for **cross-project-federation**.
- [ ] 3.1 Define data contracts, permissions, idempotency and API surface for **integration-designer**.
- [ ] 3.2 Implement the vertical slice for **integration-designer** behind flag `integration_designer` or its catalog-defined equivalent.
- [ ] 3.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **integration-designer**.
- [ ] 3.4 Add feature/operator documentation, metrics, and a rollback exercise for **integration-designer**.
- [ ] 4.1 Define data contracts, permissions, idempotency and API surface for **impact-analysis**.
- [ ] 4.2 Implement the vertical slice for **impact-analysis** behind flag `impact_analysis` or its catalog-defined equivalent.
- [ ] 4.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **impact-analysis**.
- [ ] 4.4 Add feature/operator documentation, metrics, and a rollback exercise for **impact-analysis**.
- [ ] 5.1 Define data contracts, permissions, idempotency and API surface for **ai-evaluations**.
- [ ] 5.2 Implement the vertical slice for **ai-evaluations** behind flag `ai_evaluations` or its catalog-defined equivalent.
- [ ] 5.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **ai-evaluations**.
- [ ] 5.4 Add feature/operator documentation, metrics, and a rollback exercise for **ai-evaluations**.

## Phase exit gates
- [ ] X.1 Review security and threats; verify default-deny policies and data minimization.
- [ ] X.2 Measure latency, budgets, and freshness against the phase-specific SLOs.
- [ ] X.3 Demonstrate project A/B isolation, auditability and reproducible evidence.
- [ ] X.4 Enable for a pilot project only; confirm rollback works.

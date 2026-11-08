# Implementation tasks

Change: **phase-01-foundation**. All items start unchecked. Trace them to code and test evidence.

## Domain implementation
- [ ] 1.1 Define data contracts, permissions, idempotency and API surface for **organizations**.
- [ ] 1.2 Implement the vertical slice for **organizations** behind flag `organizations` or its catalog-defined equivalent.
- [ ] 1.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **organizations**.
- [ ] 1.4 Add feature/operator documentation, metrics, and a rollback exercise for **organizations**.
- [ ] 2.1 Define data contracts, permissions, idempotency and API surface for **project-boundaries**.
- [ ] 2.2 Implement the vertical slice for **project-boundaries** behind flag `project_boundaries` or its catalog-defined equivalent.
- [ ] 2.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **project-boundaries**.
- [ ] 2.4 Add feature/operator documentation, metrics, and a rollback exercise for **project-boundaries**.
- [ ] 3.1 Define data contracts, permissions, idempotency and API surface for **identity-policy**.
- [ ] 3.2 Implement the vertical slice for **identity-policy** behind flag `identity_policy` or its catalog-defined equivalent.
- [ ] 3.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **identity-policy**.
- [ ] 3.4 Add feature/operator documentation, metrics, and a rollback exercise for **identity-policy**.
- [ ] 4.1 Define data contracts, permissions, idempotency and API surface for **feature-flags**.
- [ ] 4.2 Implement the vertical slice for **feature-flags** behind flag `feature_flags` or its catalog-defined equivalent.
- [ ] 4.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **feature-flags**.
- [ ] 4.4 Add feature/operator documentation, metrics, and a rollback exercise for **feature-flags**.
- [ ] 5.1 Define data contracts, permissions, idempotency and API surface for **audit-provenance**.
- [ ] 5.2 Implement the vertical slice for **audit-provenance** behind flag `audit_provenance` or its catalog-defined equivalent.
- [ ] 5.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **audit-provenance**.
- [ ] 5.4 Add feature/operator documentation, metrics, and a rollback exercise for **audit-provenance**.
- [ ] 6.1 Define data contracts, permissions, idempotency and API surface for **canonical-events**.
- [ ] 6.2 Implement the vertical slice for **canonical-events** behind flag `canonical_events` or its catalog-defined equivalent.
- [ ] 6.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **canonical-events**.
- [ ] 6.4 Add feature/operator documentation, metrics, and a rollback exercise for **canonical-events**.
- [ ] 7.1 Define data contracts, permissions, idempotency and API surface for **ui-workspaces**.
- [ ] 7.2 Implement the vertical slice for **ui-workspaces** behind flag `ui_workspaces` or its catalog-defined equivalent.
- [ ] 7.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **ui-workspaces**.
- [ ] 7.4 Add feature/operator documentation, metrics, and a rollback exercise for **ui-workspaces**.
- [ ] 8.1 Define data contracts, permissions, idempotency and API surface for **llm-gateway**.
- [ ] 8.2 Implement the vertical slice for **llm-gateway** behind flag `llm_gateway` or its catalog-defined equivalent.
- [ ] 8.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **llm-gateway**.
- [ ] 8.4 Add feature/operator documentation, metrics, and a rollback exercise for **llm-gateway**.

## Phase exit gates
- [ ] X.1 Review security and threats; verify default-deny policies and data minimization.
- [ ] X.2 Measure latency, budgets, and freshness against the phase-specific SLOs.
- [ ] X.3 Demonstrate project A/B isolation, auditability and reproducible evidence.
- [ ] X.4 Enable for a pilot project only; confirm rollback works.

# Implementation tasks

Change: **phase-02-connectors**. All items start unchecked. Trace them to code and test evidence.

## Domain implementation
- [ ] 1.1 Define data contracts, permissions, idempotency and API surface for **connector-platform**.
- [ ] 1.2 Implement the vertical slice for **connector-platform** behind flag `connector_platform` or its catalog-defined equivalent.
- [ ] 1.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **connector-platform**.
- [ ] 1.4 Add feature/operator documentation, metrics, and a rollback exercise for **connector-platform**.
- [ ] 2.1 Define data contracts, permissions, idempotency and API surface for **source-code-discovery**.
- [ ] 2.2 Implement the vertical slice for **source-code-discovery** behind flag `source_code_discovery` or its catalog-defined equivalent.
- [ ] 2.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **source-code-discovery**.
- [ ] 2.4 Add feature/operator documentation, metrics, and a rollback exercise for **source-code-discovery**.
- [ ] 3.1 Define data contracts, permissions, idempotency and API surface for **runtime-discovery**.
- [ ] 3.2 Implement the vertical slice for **runtime-discovery** behind flag `runtime_discovery` or its catalog-defined equivalent.
- [ ] 3.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **runtime-discovery**.
- [ ] 3.4 Add feature/operator documentation, metrics, and a rollback exercise for **runtime-discovery**.
- [ ] 4.1 Define data contracts, permissions, idempotency and API surface for **data-topology**.
- [ ] 4.2 Implement the vertical slice for **data-topology** behind flag `data_topology` or its catalog-defined equivalent.
- [ ] 4.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **data-topology**.
- [ ] 4.4 Add feature/operator documentation, metrics, and a rollback exercise for **data-topology**.
- [ ] 5.1 Define data contracts, permissions, idempotency and API surface for **work-connectors**.
- [ ] 5.2 Implement the vertical slice for **work-connectors** behind flag `work_connectors` or its catalog-defined equivalent.
- [ ] 5.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **work-connectors**.
- [ ] 5.4 Add feature/operator documentation, metrics, and a rollback exercise for **work-connectors**.
- [ ] 6.1 Define data contracts, permissions, idempotency and API surface for **document-parsing**.
- [ ] 6.2 Implement the vertical slice for **document-parsing** behind flag `document_parsing` or its catalog-defined equivalent.
- [ ] 6.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **document-parsing**.
- [ ] 6.4 Add feature/operator documentation, metrics, and a rollback exercise for **document-parsing**.
- [ ] 7.1 Define data contracts, permissions, idempotency and API surface for **normalization-freshness**.
- [ ] 7.2 Implement the vertical slice for **normalization-freshness** behind flag `normalization_freshness` or its catalog-defined equivalent.
- [ ] 7.3 Add positive/negative scenarios, tenant isolation and failure-injection tests for **normalization-freshness**.
- [ ] 7.4 Add feature/operator documentation, metrics, and a rollback exercise for **normalization-freshness**.

## Phase exit gates
- [ ] X.1 Review security and threats; verify default-deny policies and data minimization.
- [ ] X.2 Measure latency, budgets, and freshness against the phase-specific SLOs.
- [ ] X.3 Demonstrate project A/B isolation, auditability and reproducible evidence.
- [ ] X.4 Enable for a pilot project only; confirm rollback works.

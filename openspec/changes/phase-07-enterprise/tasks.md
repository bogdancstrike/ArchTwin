# Implementation tasks — phase-07-enterprise

Legend: **[Beta]** required for M4 enterprise beta · **[Later]** on demand. Check a task only with merged code and green tests.

## 1. Enterprise operations — AT-ENTERPRISE_OPERATIONS-001..003
- [ ] 1.1 [Beta] Helm chart with values profiles; Pod security (non-root, read-only rootfs, seccomp), NetworkPolicies, resource limits.
- [ ] 1.2 [Beta] CloudNativePG cluster + PITR; restore verification job (counts, checksums, audit verify, policy smoke).
- [ ] 1.3 [Beta] SLOs as code (recording rules, burn-rate alerts), Grafana dashboards.
- [ ] 1.4 [Beta] Retention, legal hold, connector deletion with secret revocation, project deletion workflow.
- [ ] 1.5 [Beta] Load tests (k6 + synthetic ingestion) for profile M; results recorded.

## 2. Collaboration — AT-COLLABORATION_APPROVALS-001..003
- [ ] 2.1 [Beta] Comments, mentions (members only), review assignments; optimistic concurrency with diff.
- [ ] 2.2 [Beta] Configurable approvers and separation of duties for baselines, ADRs, federation.
- [ ] 2.3 [Beta] Notification links re-check authorization; minimal push bodies.

## 3. Search and portability — AT-UNIFIED_SEARCH_EXPORT-001..003
- [ ] 3.1 [Beta] Scoped search (FTS + pgvector) with ACL re-check; no counts leak.
- [ ] 3.2 [Beta] Export bundle (graph JSON, DSL, Mermaid, Markdown/MADR, manifest) + re-import test.
- [ ] 3.3 [Later] Public read API + signed outgoing webhooks with idempotency keys.

## 4. Connector SDK — AT-CONNECTOR_SDK-001..003
- [ ] 4.1 [Later] Out-of-process plugin protocol, conformance kit, compatibility negotiation.
- [ ] 4.2 [Later] cosign signature verification + org allowlist; sandbox with declared egress.
- [ ] 4.3 [Later] Quarantine/dead-letter UI for failing plugins.

## 5. Architecture health — AT-ARCHITECTURE_HEALTH-001..003
- [ ] 5.1 [Beta] Scorecards with versioned metric definitions and coverage display (rendered with the diagram-design chart types).
- [ ] 5.2 [Later] Trends with definition-change markers; portfolio rollups with minimum group size.

## X. Phase exit gates
- [ ] X.1 Restore drill meets RPO/RTO.
- [ ] X.2 External penetration test findings resolved or accepted with owners.
- [ ] X.3 Load test M profile within NFRs.

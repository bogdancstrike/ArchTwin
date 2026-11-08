# Implementation tasks — phase-05-delivery

Legend: **[MVP]** required for M2 · **[Later]** may slip. Check a task only with merged code and green tests.

## 1. Planning — AT-ARCHITECTURE_PLANNING-001..003
- [ ] 1.1 [MVP] Initiative → milestone → change → work item hierarchy with owners/dates; planned elements shown distinctly in diagrams.
- [ ] 1.2 [MVP] Change approval status linked to ADR versions; no implied approval.
- [ ] 1.3 [Later] Strategic goals/capabilities layer; cost estimates.

## 2. Issue synchronization — AT-ISSUE_SYNCHRONIZATION-001..003
- [ ] 2.1 [MVP] Canonical work items from GitHub/GitLab issues; status mapping tables; unmapped status flag.
- [ ] 2.2 [Later] Jira and Taiga sync (webhooks + polling) reusing phase-02 adapters.
- [ ] 2.3 [MVP] Explicit link UI + deterministic issue-key detection in branches/PRs/commits.
- [ ] 2.4 [Later] Write-back workflow: preview, approval signal, idempotency key, audit; per-provider flag.

## 3. Implementation traceability — AT-IMPLEMENTATION_TRACEABILITY-001..003
- [ ] 3.1 [MVP] Evidence chain builder (issue → PR/MR → commit → build → digest → workload → observed edge).
- [ ] 3.2 [MVP] Stage computation incl. rolled-back detection; "unverified deployment" state.
- [ ] 3.3 [Later] Plan-change impact: orphaned tasks, stale ADRs.

## 4. Release gates — AT-RELEASE_GATES-001..003
- [ ] 4.1 [MVP] `/gates/check` API + GitHub Action and GitLab CI template producing SARIF (report-only).
- [ ] 4.2 [Later] cosign-signed results + verification step in CI templates.
- [ ] 4.3 [Later] Opt-in blocking per project/environment with deterministic rules and explicit unknown policy.

## X. Phase exit gates
- [ ] X.1 Fixture demo: initiative → issue → PR → deploy → verified; Done-but-not-deployed shows unverified.
- [ ] X.2 No remote write possible without flag + approval (security test).
- [ ] X.3 SARIF visible in a GitHub PR on the fixture repo.

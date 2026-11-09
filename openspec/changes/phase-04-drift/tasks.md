# Implementation tasks — phase-04-drift

Legend: **[MVP]** required for M2 · **[Later]** may slip. Check a task only with merged code and green tests.

## 1. Drift engine — AT-DRIFT_ENGINE-001..004
- [x] 1.1 [MVP] Rule catalog (id, version, required coverage, default severity) and first rules: missing element, unplanned element, edge added/removed, protocol changed.
- [x] 1.2 [MVP] Three-way evaluator with coverage/freshness → `unknown`/`incomplete`; truth-table unit tests (table in `design.md`).
- [x] 1.3 [MVP] Stable finding identity; idempotent re-evaluation test (same snapshots ⇒ same IDs).
- [x] 1.4 [MVP] Accept-as-intended (updates baseline via reviewed command) and scoped, expiring suppressions.
- [ ] 1.5 [Later] Contract (OpenAPI/AsyncAPI breaking change), ownership and trust-boundary rules.

## 2. Watchers and reconciliation — AT-CONTINUOUS_WATCHERS-001..003
- [x] 2.1 [MVP] Debounced `DriftEvaluationWorkflow` triggered by `inventory.changed`; scheduled full reconcile.
- [ ] 2.2 [MVP] Burst test: 10k duplicate webhooks ⇒ bounded evaluations, no starvation of another project.
- [x] 2.3 [MVP] Connector outage ⇒ stale, no deletion drift; recovery ⇒ full reconcile before deletions are allowed.

## 3. Triage — AT-DRIFT_TRIAGE-001..003
- [x] 3.1 [MVP] Finding states (new, acknowledged, investigating, accepted, resolved, suppressed), assignment, comments, reopen-on-recurrence.
- [x] 3.2 [MVP] Evidence view: baseline version, compared snapshots, rule version, source changes (commit/deployment).
- [ ] 3.3 [Later] Priority score with explanation; inferred-evidence cap.

## 4. Notifications — AT-ARCHITECTURE_NOTIFICATIONS-001..003
- [x] 4.1 [MVP] In-app notifications via SSE; dedupe with occurrence count.
- [ ] 4.2 [Later] Apprise delivery (email, Slack, Teams, webhook) with retries, dead-letter, quiet hours, digests; authorization re-check at send time.
- [ ] 4.3 [MVP] Prometheus metrics + Grafana dashboard: event→finding latency, scan lag, freshness, FP rate.

## X. Phase exit gates
- [ ] X.1 Fixture drift demo: merge a route/topic change → finding with evidence; stop a connector → `unknown`, no false deletion.
- [ ] X.2 Observe-only period completed; FP rate below threshold before enabling notifications.
- [ ] X.3 Latency p50/p95 recorded vs NFR.
- [ ] X.4 Rollback rehearsal (notifications off, engine off, rule version revert).

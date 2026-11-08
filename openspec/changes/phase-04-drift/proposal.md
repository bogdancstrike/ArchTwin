# Proposal: Continuous drift and early-warning intelligence

## Why
Drift detection is ArchTwin's strongest wedge (see `docs/strategy/PRODUCT_POSITIONING.md`): telling an architect *promptly and correctly* that what runs no longer matches what was decided. It is also the biggest trust risk — noisy or false alerts kill adoption faster than missing features. This phase adds deterministic three-way drift (desired / code / runtime), watchers, triage and notifications, with false-positive controls designed in from the start.

Users affected: architects, platform/SRE, tech leads, security architects.

## What Changes
- Add **Desired, observed and implemented architecture drift** (`drift-engine`).
- Add **Near-real-time watchers and reconciliation** (`continuous-watchers`).
- Add **Drift scoring and lifecycle** (`drift-triage`).
- Add **Architecture alerts and digests** (`architecture-notifications`).

## Impact
- **Modules:** `drift` (rules, evaluation, findings, suppressions), `notifications`.
- **Tables:** drift_rules (versioned), drift_evaluations, drift_findings (stable identity = rule_id + entity keys + environment), finding_events, suppressions (scope, reason, reviewer, expiry), notification_routes, deliveries.
- **Temporal workflows:** `DriftEvaluationWorkflow` (debounced per project/environment), `DigestWorkflow` (schedule), `DeliveryWorkflow` (retries, dead-letter).
- **Adopted OSS:** Apprise (email, Slack, Teams, webhooks and 100+ targets), SSE via `sse-starlette`, Prometheus metrics + Grafana dashboards for SLOs.
- **Flags:** `module.drift-engine`, `module.continuous-watchers`, `module.drift-triage`, `module.architecture-notifications`, `drift.email_alerts`, `drift.external_webhook_alerts`, `connectors.webhooks`.

## Dependencies
Phases 01–03 (observations with freshness, graph, approved baselines).

## Security risks
Alert payloads leaking restricted details; alert floods (DoS on people); suppressions used to hide real problems.

## Rollout and rollback
1. **Observe-only**: findings computed and stored, visible to the project owner only, no notifications.
2. Measure false-positive rate on the fixture and pilot; tune rules.
3. Enable in-app notifications, then email/webhook per project.
Rollback: disable notification flags (findings keep computing) or the engine flag (UI shows "monitoring disabled").

## Success
- Fixture scenarios: route change, topic change, removed service, stopped connector → correct finding or `unknown`, never a false deletion.
- p95 event-to-finding latency measured and within the NFR target under normal source availability.
- False-positive rate on the labelled fixture below the agreed threshold before notifications are enabled.

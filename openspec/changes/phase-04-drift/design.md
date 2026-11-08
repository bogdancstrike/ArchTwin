# Design: Continuous drift and early-warning intelligence

## Context
Implements `specs/` of this change. ADR-0003 (three-way evidence model) applies. Sequence diagram: `docs/architecture/drift-and-ai-sequences.mmd`.

## Goals / Non-goals
- **Goals:** deterministic, reproducible drift; UNKNOWN/INCOMPLETE semantics; triage lifecycle; deduplicated notifications; measurable latency and false-positive rate.
- **Non-goals:** AI-detected drift, auto-remediation, CI blocking (phase 05).

## Evaluation model
Input: `{baseline_snapshot?, static_snapshot, runtime_snapshot, environment, coverage(per connector), rule_set_version}`.
Output: findings with stable identity `hash(rule_id, entity_keys, environment)` so re-evaluation of the same inputs is idempotent.

**Truth table per element/edge** (simplified):

| Desired | Static (code) | Runtime | Coverage | Result |
|---|---|---|---|---|
| present | present | present | complete | in sync |
| present | absent | absent | complete | `missing` drift |
| absent | present | present | complete | `unplanned` drift |
| present | present | — | runtime stale | `unknown` (no alert) |
| present | present | absent | runtime incomplete | `incomplete` (no alert) |
| protocol A | protocol B | protocol B | complete | `protocol-changed` drift |

## Decisions

| # | Decision | Adopted OSS | Notes |
|---|---|---|---|
| D1 | Rules are versioned Python predicates registered in a rule catalog (id, version, severity defaults, required coverage) | — | A generic rules engine (Drools-style, OPA) adds indirection without benefit for graph comparisons; OPA stays an option for org policy packs later |
| D2 | Evaluation runs in a Temporal workflow, debounced (e.g., 30–60 s) per project/environment, plus scheduled full reconcile | Temporal | Coalesces event bursts (10k webhooks → few evaluations) |
| D3 | First scan after connecting is **observe-only**; no findings until a baseline exists or a second snapshot confirms state | — | Avoids day-one noise |
| D4 | Grace windows for rollouts (configurable; default 10 min) and K8s UID recreation handling | — | — |
| D5 | Priority score = explicit weighted factors (environment, criticality, exposure, magnitude, confidence); inferred-only evidence capped | — | Score explanation stored with finding |
| D6 | Notifications via outbox → `DeliveryWorkflow` → **Apprise**; payloads contain a link + non-sensitive summary only | Apprise | No custom Slack/Teams/email integrations |
| D7 | In-app live updates via SSE | sse-starlette | Same as Horizon |
| D8 | KPIs as Prometheus metrics: event→finding latency (histogram), scan lag, connector freshness ratio, FP rate per rule; Grafana dashboard JSON committed | Prometheus, Grafana | — |

## Threat controls
Authorization re-check at delivery time; minimal payloads; rate limits and digests; suppressions require reason, reviewer and expiry and are audited.

## Risks / trade-offs
| Risk | Mitigation |
|---|---|
| False positives destroy trust | observe-only stage, coverage semantics, grace windows, FP tracking per rule, rule rollback by version |
| Detection latency promises not met | Measure from provider event receipt; publish p50/p95; never promise real time |
| Too many findings to triage | Grouping by root change (commit/deployment), digests, priority score |

## Rollback
Disable notifications (engine keeps evaluating) or the engine (UI banner "monitoring disabled"); revert a rule to a previous version; findings keep their rule version.

## Open questions
- Default grace window and debounce per connector type — calibrate on fixture and first pilot.

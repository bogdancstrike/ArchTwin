# Nonfunctional requirements and pilot SLOs

These are proposed acceptance targets, to be validated against benchmark workloads before commercial claims.

| Attribute | MVP acceptance target | Measurement |
|---|---|---|
| Service availability | ≥99.5% monthly pilot target; no AI gateway dependency for static reads | synthetic API checks / incident logs |
| Small graph query | p95 < 750ms for projects ≤5k nodes / 20k edges | seeded benchmark, warmed/cache-cold samples |
| Medium graph diagram | p95 < 4s for 2k rendered elements with aggregation/virtualization | browser render and server graph query |
| Drift recognition | p95 <5 minutes from signed event receipt to finding under normal source availability | timestamps at webhook, snapshot, rule, alert |
| Source freshness | Git/K8s ≤5 min normal target; work trackers ≤15 min; nightly reconcile | last-observed/source cursor lag |
| Document ingestion | ≤2 min for a 30-page typical native PDF after queue admission | Docling parse, storage/index timings |
| AI Q&A | p95 <60s for medium evidence pack; streaming response when feasible | Langfuse trace / wall time |
| Security | 0 cross-project data leaks and 0 unauthorized write operations in test corpus | red-team + property tests |
| Reliability | zero lost committed source events after worker crash; idempotent replays | fault-injection / outbox tests |
| Backup/restore | RPO 15 min, RTO 2h initial deployment target | quarterly recovery exercise |
| Audit integrity | 100% sensitive mutation coverage in defined action catalog | audit completeness assertions |
| Accessibility | WCAG 2.2 AA target for core flows, graph alternative table | automated and manual audit |

## Capacity test profiles
- S: 1 org, 3 projects, 10 services/project, 100 work items, 1k source observations/day.
- M: 5 orgs, 50 projects, 100 services/project, 10k work items, 100k observations/day.
- L: 20 orgs, 500 projects, 1000 services/project, 1M work items, 1M+ observations/day (future target, only after profiling).

## Load and chaos tests
- 100 concurrent project and graph searches; 30 concurrent diagram generation jobs; bursts of 10k identical webhook deliveries; 10 clients revoking access while reading; 3 failed connectors and one slow PDP; 10k-edge cycle; partial Postgres failover; Langfuse down; LiteLLM overloaded; Docker/K8s connector unavailable; malicious PDF and XSS in issue titles.
- Measure SLO per project/organization, not aggregate only. Cache keys must include authorization revision and scope. Use bounded worker concurrency and fair queues.

## Definition of ready
Requirements, policy matrix, source/provenance mappings, API contracts, flag dependencies, initial UX and failure scenarios reviewed.

## Definition of done
Tests for positive/negative scenarios; threat checks; executable migration; OpenAPI update; metrics and logging; feature flag OFF and ON tests; accessibility review; load baseline; rollback plan; evidence links from tasks to code/CI/deployment; reviewer sign-off; spec archived only after real implementation.

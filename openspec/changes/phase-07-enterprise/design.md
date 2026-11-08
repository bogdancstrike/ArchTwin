# Design: Enterprise operations and extensibility

## Context
Implements `specs/` of this change. Deployment blueprint: `docs/ops/DEPLOYMENT_BLUEPRINT.md`; NFRs: `docs/acceptance/NFR_SLOS.md`.

## Goals / Non-goals
- **Goals:** HA deployment, verified backups, retention/legal hold, collaboration, scoped search, portable exports, plugin SDK with sandboxing, health/portfolio views.
- **Non-goals:** multi-region active-active, a public marketplace with payments, SaaS multi-tenancy at scale before demand.

## Decisions

| # | Decision | Adopted OSS | Notes |
|---|---|---|---|
| D1 | Kubernetes deployment via one Helm chart (api, worker, web, docling, renderers) with values profiles | Helm | Compose remains the dev/pilot profile |
| D2 | PostgreSQL HA + PITR via CloudNativePG (or managed Postgres) | CloudNativePG, Barman | No custom backup scripts beyond a verification job |
| D3 | Restore verification job: counts, checksums, audit chain verify, policy smoke tests | — | Run quarterly and after major upgrades |
| D4 | Collaboration: comments/mentions/assignments with optimistic concurrency (revisions + diff), no CRDT real-time editing | — | Yjs considered later if users demand live co-editing |
| D5 | Search: PostgreSQL FTS + pgvector with scope filters before ranking; re-check authorization on results | PostgreSQL | OpenSearch only if measured need |
| D6 | Plugins run **out of process** as separate containers implementing the connector SDK over HTTP/gRPC; manifest declares egress; images signed and verified with cosign; org allowlist | cosign, NetworkPolicy | In-process Python plugins rejected (no isolation) |
| D7 | Portability: canonical graph JSON (versioned schema), Structurizr DSL, Mermaid, Markdown/MADR, bundle manifest with hashes | — | Re-import test in CI |
| D8 | Health metrics have versioned definitions; portfolio aggregates enforce minimum group size | — | — |
| D9 | SLOs as code (Prometheus recording rules + burn-rate alerts), Grafana dashboards committed | Prometheus, Grafana | — |

## Capacity plan
Start with 3–10 services per project; load-test 50 projects / 5k-node graphs (k6 for API, synthetic observations for ingestion) before claiming enterprise scale. Introduce Neo4j/Qdrant projections or Kafka only when an ADR shows measured need.

## Risks / trade-offs
| Risk | Mitigation |
|---|---|
| Building enterprise features before product-market fit | Phase gated by the M2/M3 decision rule |
| Plugin sandbox escapes | container isolation, no service-account token, egress policy, signature verification |
| Restore that "works" but is unreadable | key availability check + verification job |

## Rollback
Helm rollback; feature flags; plugin deactivation per org.

## Open questions
- Managed Postgres vs CloudNativePG per customer environment.

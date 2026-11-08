# Design: Discovery and connected evidence

## Context
Implements `specs/` of this change on top of phase 01. Contracts: `docs/connectors/CONNECTOR_CONTRACT.md`, provider plan: `docs/connectors/CONNECTOR_MATRIX.md`, data model: `docs/architecture/DATA_MODEL.md`.

## Goals / Non-goals
- **Goals:** a small, well-tested connector SDK; P1 adapters (GitHub, GitLab, Kubernetes, PostgreSQL, Kafka, OpenAPI URL, file upload); read-only Jira/Taiga basics; immutable observations with provenance and freshness.
- **Non-goals:** write-back, cloud provider inventories, perfect call-graph analysis, a generic ETL framework.

## Pipeline
```
trigger (webhook | K8s watch | Temporal Schedule poll | manual)
  → Temporal workflow (per connector, per project; activity re-checks flag + entitlement)
  → adapter.fetch()   bounded, paginated, rate-limited, via egress guard
  → raw artifact → object store (sha256 key) + source_artifacts row
  → adapter.normalize(raw, mapping_version) → Observation[]   (pure function, unit-testable)
  → observations INSERT (append-only, idempotent on natural key) + outbox `inventory.changed`
  → cursor/checkpoint committed AFTER durable storage
```

## Decisions

| # | Decision | Adopted OSS | Notes / rejected alternatives |
|---|---|---|---|
| D1 | Connector SDK = small Python `Protocol` (`test`, `discover`, `normalize`, `verify_event`, `health`) + manifest (capabilities, scopes, egress hosts, data classes, versions) | — | Airbyte/Meltano/Singer evaluated: they move *rows* into warehouses, not architecture metadata with provenance; too heavy for this purpose |
| D2 | Every sync is a Temporal workflow; schedules use Temporal Schedules | Temporal | Gives retries, timeouts, heartbeats, cancellation and visibility; no custom scheduler |
| D3 | GitHub via GitHub App installation (fine-grained, read-only) | githubkit (async, typed) | PATs allowed only for dev |
| D4 | GitLab via OAuth app / project access token | python-gitlab | — |
| D5 | Code extraction runs on a **shallow clone in an ephemeral sandbox** (no network, CPU/time limits) | git CLI, tree-sitter, Syft | Syft produces a CycloneDX SBOM → library dependencies for free. Framework detectors (Spring, FastAPI, Express, Kafka clients, JDBC/SQLAlchemy URLs) are tree-sitter queries versioned as `parser_version`. Existing OpenAPI/AsyncAPI files, `catalog-info.yaml` (Backstage), Dockerfiles, Helm charts and CODEOWNERS are parsed directly — they are the highest-confidence static evidence |
| D6 | Kubernetes: list + watch with `resourceVersion`; relist on 410 Gone | kubernetes_asyncio | Read-only ClusterRole template shipped in `deploy/kubernetes/archtwin-reader.yaml` |
| D7 | Runtime call edges come from **OpenTelemetry service-graph metrics** (`traces_service_graph_request_total{client,server}`) via the Prometheus HTTP API, or Jaeger/Tempo dependency APIs | OTel Collector `servicegraph` connector, Prometheus | Reuses what platform teams already run; no eBPF/agent of our own |
| D8 | Databases: catalog-only reflection in a read-only transaction | SQLAlchemy `inspect()` per dialect | Never `SELECT` from user tables; excess privilege is reported |
| D9 | Kafka: metadata only (topics, partitions, consumer groups, offsets lag) + Schema Registry subjects | confluent-kafka AdminClient, schema registry client | Never consume payloads |
| D10 | Documents: upload → magic-byte type check → size/decompression limits → optional ClamAV → Docling in an isolated container → passages with page provenance | Docling, python-magic, ClamAV | Same isolation pattern as Horizon's `deploy/docling` |
| D11 | Webhook ingress: provider signature verification (HMAC/JWT), replay window, `(connector_id, delivery_id)` dedupe, then enqueue | — | Raw body stored only after verification |
| D12 | Egress guard for all connector HTTP: allowlisted hosts from manifest + org policy, DNS resolution pinned per request, redirect re-validation, deny RFC1918/link-local/loopback unless explicitly allowed for on-prem targets | httpx transport hook | Same approach as Horizon's SSRF-guarded fetcher |
| D13 | Identity reconciliation static ↔ runtime: deterministic keys first (image name ↔ repo, `app.kubernetes.io/name` ↔ service name, Backstage annotations), then a **reviewable** suggestion queue; never auto-merge ambiguous matches | — | Spike S3 measures match rate on the fixture |
| D14 | Freshness: each connector declares a freshness SLA; observations older than it are `stale`; partial/failed scans mark coverage `incomplete` | — | Basis for UNKNOWN semantics in drift and AI |

## Observation contract
See `docs/connectors/CONNECTOR_CONTRACT.md`. Natural idempotency key: `(connector_id, resource_kind, provider_resource_id, provider_revision)`. Older revisions never overwrite newer canonical state.

## Threat controls
Least-privilege scope display before activation; secrets via phase-01 envelope encryption; egress guard; sandboxed parsers; untrusted text labelled `untrusted_source_text` for later AI; canary-secret scan; webhook signature tests.

## Risks / trade-offs
| Risk | Mitigation |
|---|---|
| Static extraction accuracy too low to be useful | Prioritize declared artifacts (OpenAPI, AsyncAPI, Helm, catalog-info) over inference; measure precision/recall on fixture repos (spike S2); show confidence |
| Connector breadth explodes scope | Only P1 adapters in this phase; others need a measured request |
| Provider API rate limits | Per-provider token buckets in Valkey; conditional requests (ETag); incremental sync |
| Large repos make scans slow | Shallow clone, path filters, incremental by changed files, time budget per scan |
| Docling resource spikes | Separate container with limits and queue concurrency 1–2 |

## Rollback
Disable the provider flag; workflows stop at the next activity; observations stay (stale). Mapping versions allow re-normalizing raw artifacts after a fix without re-fetching.

## Open questions
- Which languages beyond Java/Python/TypeScript for the first pilot? Decide from design-partner repos (M0).
- Is Docker Swarm needed for the first pilot? Default: P2, implement only on demand.

# Proposal: Discovery and connected evidence

## Why
ArchTwin's value depends on **evidence**, not hand-drawn boxes. Architects need the platform to read what code declares, what is deployed and what data/messaging topology exists — safely, read-only, and with provenance — before diagrams, drift or AI can be trusted. This phase builds the connector platform and the first adapters, and produces normalized, immutable observations.

Users affected: project owners (configure connectors), architects and platform engineers (inspect inventory), security admins (approve scopes/egress).

## What Changes
- Add **Secure connector lifecycle and ingestion SDK** (`connector-platform`).
- Add **Source repository and code architecture extraction** (`source-code-discovery`).
- Add **Runtime infrastructure inventory** (`runtime-discovery`).
- Add **Database and messaging topology discovery** (`data-topology`).
- Add **GitHub/GitLab, Jira and Taiga application connectors** (`work-connectors`) — read-only.
- Add **Document and diagram import processing** (`document-parsing`).
- Add **Evidence normalization, confidence and freshness** (`normalization-freshness`).

## Impact
- **Modules:** `connectors` (SDK, registry, credentials, egress guard), `inventory` (observations, normalization), `documents` (uploads, parsing), adapters under `connectors/adapters/*`.
- **Tables:** connectors, connector_cursors, webhook_deliveries, source_artifacts (pointer + hash to object store), observations (append-only, partitioned by month), mapping_versions, documents, document_versions.
- **Temporal workflows:** `ConnectorTestWorkflow`, `BootstrapSyncWorkflow`, `IncrementalSyncWorkflow`, `ReconcileWorkflow` (Temporal Schedules), `DocumentIngestWorkflow`.
- **Infrastructure:** `docling` worker container (isolated, CPU/memory-limited), optional `clamav` profile, egress proxy for connector traffic.
- **Adopted OSS:** githubkit, python-gitlab, kubernetes_asyncio, SQLAlchemy reflection, confluent-kafka AdminClient + Schema Registry client, tree-sitter (+ language pack), Syft (CycloneDX SBOM), Docling, ClamAV, python-magic, OpenAPI/AsyncAPI parsers, OpenTelemetry service-graph metrics via the Prometheus HTTP API.
- **Flags:** `connector.*` per provider, `connectors.webhooks`, `connectors.full_reconciliation`.

## Dependencies
Phase 01 (RequestContext, Cerbos, outbox, secrets, flags, audit, Temporal).

## Security risks
Token theft, SSRF via connector URLs/redirects/DNS rebinding, malicious documents, prompt-injection text stored for later AI use, over-privileged credentials, webhook spoofing.

## Rollout and rollback
- Each provider ships behind `connector.<provider>`; first enabled for the reference fixture project only.
- Read-only scopes only; connectors detect and warn about excess privileges.
- Rollback: disable the provider flag → running workflows stop at the next activity check; observations remain immutable and stay queryable as stale.

## Success
- Against the reference fixture (OpenTelemetry Demo on kind + its Git repos + Postgres + Kafka), discovery produces services, endpoints, topics, tables and workloads with evidence links.
- Duplicate webhooks, missed webhooks, partial scans and revoked tokens behave per spec (no duplicates, no false deletions).
- Canary-secret and SSRF suites pass.

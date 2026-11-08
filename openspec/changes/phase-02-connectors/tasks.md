# Implementation tasks — phase-02-connectors

Legend: **[MVP]** required for M1 · **[Later]** may slip. Check a task only with merged code and green tests.

## 0. Reference fixture (do first — every later test uses it)
- [ ] 0.1 [MVP] `fixtures/` setup: kind cluster + OpenTelemetry Demo Helm chart (polyglot services, Kafka, Postgres, OTel collector with servicegraph connector), mirrored Git repos, `make fixtures-up` / `fixtures-down` (separate Compose project, never part of app Compose).
- [ ] 0.2 [MVP] Labelled ground truth: expected services, endpoints, topics, tables and edges in `fixtures/ground-truth.yaml` (used for precision/recall).

## 1. Connector platform — AT-CONNECTOR_PLATFORM-001..003
- [ ] 1.1 [MVP] SDK `Protocol`, manifest schema (JSON Schema), registry, conformance test kit (`connector_sdk/testing`).
- [ ] 1.2 [MVP] Credential flow on phase-01 envelope encryption; test endpoint shows scopes and excess privileges; secrets never returned.
- [ ] 1.3 [MVP] Egress guard (allowlist, DNS pinning, redirect re-check, private-range deny) + SSRF test suite (IMDS, loopback, rebinding, redirects).
- [ ] 1.4 [MVP] Temporal workflows: test, bootstrap, incremental, reconcile (Schedules); activities re-check flag + entitlement; heartbeats; cancellation.
- [ ] 1.5 [MVP] Webhook ingress with signature verification, replay window, dedupe table; metrics per connector.
- [ ] 1.6 [MVP] Partial-scan semantics: incomplete coverage never tombstones; tombstone only after a complete authorized scan.

## 2. Normalization and freshness — AT-NORMALIZATION_FRESHNESS-001..003
- [ ] 2.1 [MVP] Observation table (append-only, monthly partitions), mapping versions, schema validation before commit.
- [ ] 2.2 [MVP] Freshness SLA per connector; `current | stale | incomplete | unknown` computed in one place and exposed via API.
- [ ] 2.3 [MVP] Conflict retention: contradictory observations both stored and surfaced.
- [ ] 2.4 [Later] Re-normalize from stored raw artifacts when a mapping version changes (Temporal batch workflow).

## 3. Source code discovery — AT-SOURCE_CODE_DISCOVERY-001..003
- [ ] 3.1 [MVP] GitHub App + GitLab adapters: repos, refs, selected branches, push/PR/MR webhooks.
- [ ] 3.2 [MVP] Sandbox clone + declared-artifact parsers: OpenAPI, AsyncAPI, Dockerfile, Helm/Kustomize manifests, `catalog-info.yaml`, CODEOWNERS.
- [ ] 3.3 [MVP] Syft SBOM → library dependencies; tree-sitter detectors for Spring/FastAPI/Express routes, Kafka producer/consumer, DB client URLs (versioned `parser_version`, line-range evidence).
- [ ] 3.4 [MVP] Precision/recall report vs fixture ground truth in CI (target set in spike S2).
- [ ] 3.5 [Later] Additional languages (Go, .NET) on demand.

## 4. Runtime discovery — AT-RUNTIME_DISCOVERY-001..003
- [ ] 4.1 [MVP] Kubernetes adapter: deployments, statefulsets, services, ingresses, configmaps (names only), labels/annotations, image digests; watch + relist.
- [ ] 4.2 [MVP] Read-only ClusterRole/Role templates; privilege check warns on cluster-admin.
- [ ] 4.3 [MVP] OTel service-graph adapter (Prometheus HTTP API) → runtime `calls` edges with time window and request counts.
- [ ] 4.4 [Later] Docker Swarm adapter; ArgoCD applications.

## 5. Data topology — AT-DATA_TOPOLOGY-001..003
- [ ] 5.1 [MVP] PostgreSQL catalog reflection (schemas, tables, FKs) in read-only transaction; MySQL via the same SQLAlchemy path.
- [ ] 5.2 [MVP] Kafka topics/consumer groups/lag + Schema Registry subjects; producers/consumers only from code or runtime evidence, otherwise unknown.
- [ ] 5.3 [MVP] Sensitive-metadata classifier (column-name rules + manual tags) → masked in UI/search/AI.
- [ ] 5.4 [Later] MongoDB, Elasticsearch/OpenSearch, Neo4j, Qdrant metadata adapters.

## 6. Work connectors (read-only) — AT-WORK_CONNECTORS-001..003
- [ ] 6.1 [MVP] GitHub/GitLab issues + PR/MR metadata.
- [ ] 6.2 [Later] Jira (Cloud + DC) and Taiga read-only adapters with webhook signature checks and polling fallback.
- [ ] 6.3 [MVP] Write-back structurally absent: no write scopes requested; enabling write-back refused in this phase.

## 7. Document parsing — AT-DOCUMENT_PARSING-001..003
- [ ] 7.1 [MVP] Upload API with magic-byte validation, size and decompression limits; object store per org/project prefix.
- [ ] 7.2 [MVP] Docling container + `DocumentIngestWorkflow`; passages with page provenance; versioned documents.
- [ ] 7.3 [Later] ClamAV profile; quarantine path; malicious-file test corpus.

## X. Phase exit gates
- [ ] X.1 Fixture discovery demo: inventory with evidence links, freshness badges, and an intentionally stopped connector showing `stale`.
- [ ] X.2 SSRF, canary-secret, webhook-signature and duplicate/missed-event suites green.
- [ ] X.3 Precision/recall on fixture recorded; thresholds agreed for M1.
- [ ] X.4 Provider flag OFF mid-sync stops work safely; rollback rehearsed.

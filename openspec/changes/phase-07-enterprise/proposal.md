# Proposal: Enterprise operations and extensibility

## Why
Pilots prove value; enterprises need reliability, recovery, collaboration, search, portability, extensibility and portfolio views before they depend on a tool. This phase hardens ArchTwin for multi-org production use — and only starts after M2/M3 show sustained usage (see decision rule in `docs/strategy/PRODUCT_POSITIONING.md`).

Users affected: org admins, operators/SRE, security, enterprise architects, connector developers.

## What Changes
- Add **Reliability, scale, backup and retention** (`enterprise-operations`).
- Add **Multi-user collaboration, comments and approvals** (`collaboration-approvals`).
- Add **Unified search, discovery and portability** (`unified-search-export`).
- Add **Extension SDK and connector marketplace model** (`connector-sdk`).
- Add **Architecture health and portfolio insights** (`architecture-health`).

## Impact
- **Modules:** `ops` (SLOs, backup verification, retention), `collaboration`, `search`, `plugins`, `health`.
- **Infrastructure:** Helm chart for Kubernetes; CloudNativePG (PostgreSQL HA, PITR backups) or managed Postgres; Temporal HA; OpenTelemetry Collector, Prometheus, Grafana, Loki/Tempo; optional OpenBao.
- **Adopted OSS:** Helm, CloudNativePG, pgBackRest/Barman (via CNPG), Velero (optional cluster backup), Sigstore cosign (plugin signing), Kubernetes NetworkPolicy, Grafana SLO dashboards, PostgreSQL FTS/pgvector for search.
- **Flags:** `module.enterprise-operations`, `module.collaboration-approvals`, `module.unified-search-export`, `module.connector-sdk`, `module.architecture-health`, `ui.portfolio`, `ui.executive_dashboard`, and P3 `connector.*` flags.

## Dependencies
Phases 01–06 (health and portfolio rely on drift, traceability and federation).

## Security risks
Plugin supply chain, search leakage across projects, portfolio aggregation exposing single-project data, restore with wrong keys/policies.

## Rollout and rollback
Helm chart first used for a staging pilot; restore drills before declaring RPO/RTO; plugins only from an org allowlist and signed. Rollback via Helm revision + flags.

## Success
- Quarterly restore drill meets RPO 15 min / RTO 2 h targets with policy and checksum verification.
- 50 projects / 5k-node graphs load test meets NFRs.
- A third-party connector passes the conformance kit and runs sandboxed with declared egress only.

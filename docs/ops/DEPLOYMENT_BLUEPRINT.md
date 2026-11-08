# Deployment blueprint (reference design, not executable charts)

## Local developer profile
- One `compose.yaml` (`make up`): `web` (nginx + React SPA), `api` (FastAPI), `worker` (Temporal worker + outbox relay), `postgres` (pgvector image; also hosts keycloak/temporal/litellm/langfuse databases), `temporal` + `temporal-ui`, `keycloak` (realm import), `cerbos` (policy mount), `valkey`, `seaweedfs` (S3 API), `litellm`, `langfuse-web`/`langfuse-worker` + `clickhouse`, `docling` (isolated). Profiles: `observability` (OTel collector, Prometheus, Grafana, Jaeger), `security` (ClamAV).
- `scripts/init-env.sh` generates internal secrets; only `OPENAI_API_KEY` is user-supplied; `ARCHTWIN_LLM_MODE=fake` runs without model calls (same pattern as Horizon).
- Reference fixture in a **separate** Compose/kind project (`make fixtures-up`): OpenTelemetry Demo on kind (services, Kafka, Postgres, OTel collector with servicegraph connector), mirrored Git repos, mock Jira/Taiga webhooks. Never part of application Compose.
- The first usable release MUST work without Neo4j, Qdrant or an external Kafka cluster. If Kafka is absent, PostgreSQL outbox and worker can carry modest event volumes.

## Production Kubernetes profile
- Ingress with TLS, cert-manager and network policies; React Nginx replicable separately from FastAPI.
- One Helm chart; Keycloak in HA, PostgreSQL HA + PITR via CloudNativePG or managed Postgres, Cerbos PDP as shared/sidecar deployment, Valkey, durable S3-compatible storage, workers with CPU/memory budgets.
- Temporal (HA) for all durable work; Kafka for high-volume change/event streams only when an ADR shows measured need.
- Separate connector-worker namespace or sandbox with egress restrictions; use workload identity/secrets manager. Deny access to Kubernetes API unless a connector's scoped service account explicitly needs list/watch.
- LiteLLM internal gateway with restricted egress to OpenAI; Langfuse trace storage/data retention and project privacy settings. Model provider keys are never available to API or worker processes.
- OpenTelemetry collectors, Prometheus, Jaeger/Loki/Grafana as organization-approved operators. Do not require all observability systems for initial local run.

## Kubernetes policy constraints
- `runAsNonRoot`, seccomp, read-only rootfs where practical, scoped service accounts, no privileged containers or hostPID.
- Resource limits and queue caps for Docling parsing and code analyzer workers.
- Zero-trust service-to-service access, TLS/mTLS, NetworkPolicy ingress/egress, project-specific connector credentials.
- Signed OCI images, SBOM, provenance, vulnerability gates, GitOps deployment and immutable release tags.

## Operations
- Migrations backwards-compatible and tested with old/new version overlap; require preflight schema and backup checks.
- Project-by-project flags, canary rollout, enforce no model-calling drift engine dependency, rollback via flags and versioned deployed images.
- Restore tests include object storage, PostgreSQL data, source manifests, encryption key access, authorization and graph projections.
- Connector removal must revoke external credentials and stop scheduled syncs; retain audit under retention policy.

## Sizing thought experiment
Initial load: 10 projects, ~200 services total, ~100k source observations, ~30 connectors, 5 concurrent architects. Run a load test before declaring sizing. Scale workers by queue depth and bounded provider quotas, not blindly by replica count. Postgres tuning and graph cardinality dictate when to introduce projections.

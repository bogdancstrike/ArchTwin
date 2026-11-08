# Deployment blueprint (reference design, not executable charts)

## Local developer profile
- `nginx` (React/Vite built SPA), `api` (FastAPI), `worker` (asyncio), `postgres`, `redis`, `minio`, `keycloak`, `cerbos`, `litellm`, `langfuse`, `docling-worker`; `temporal` optional when long-lived operations require it.
- Developer-only local mock GitHub/GitLab/Jira/Taiga webhook and inventory fixtures. Local cluster Kubernetes and Docker Swarm are optionally connected with read-only credentials.
- The first usable release MUST work without Neo4j, Qdrant or an external Kafka cluster. If Kafka is absent, PostgreSQL outbox and worker can carry modest event volumes.

## Production Kubernetes profile
- Ingress with TLS, cert-manager and network policies; React Nginx replicable separately from FastAPI.
- Keycloak in HA, managed PostgreSQL HA and backup, Cerbos PDP as shared/sidecar deployment, Redis, durable object storage, workers with CPU/memory budgets.
- Temporal when durable multi-hour workflows/approvals are used; Kafka for high-volume change/event streams only when measured.
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

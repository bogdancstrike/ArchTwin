# Connector support matrix

P1 = primary pilot support, P2 = second wave, P3 = optional ecosystem roadmap. This is a **plan**, not current implementation. All connector families have independent flags (`docs/feature-flags/FLAG_CATALOG.md`).

| Provider | Discovery | Authentication | Sync approach | Priority | Security |
|---|---|---|---|---|---|
| Local directory | One repo, a folder of repos, docs / architecture folders | operator-mounted read-only root | manual / reconcile; refs via `git archive` | P1 (implemented) | names-only picker, no symlink escape |
| GitHub | Repos, refs, PRs, issues, actions | App installation / fine-grained token | Webhooks + scheduled reconcile | P1 | read-only first |
| GitLab | Repos, MRs, pipelines, issues (implemented: repos/groups, branches, issues, MRs, code at any ref) | OAuth / scoped token (`read_api` + `read_repository`) | Webhooks + reconcile | P1 | read-only first |
| Jira Cloud/Data Center | Projects, issues, sprints, transitions | OAuth / token per deployment | Webhook + poll | P2 | write-back separate |
| Taiga | Projects, stories, tasks, statuses, sprints (implemented, + epics, issues) | anonymous / token / username + password | Webhook (HMAC-SHA1) + poll | P2 | write-back separate |
| Bitbucket | Repos, PRs, issues | provider token | Webhook + poll | P3 | optional |
| Azure DevOps | Repos, work items, pipelines | OAuth / PAT | Service hooks + poll | P3 | optional |
| Confluence | Spaces, pages, diagrams | OAuth / token | Poll + webhook if supported | P3 | optional |
| Notion | Pages/databases | Integration token | Poll | P3 | optional |
| Backstage | Catalog entities, owners | Scopable API key | Poll | P3 | optional |
| Kubernetes | Namespace, deployments, services, ingress, workloads | RBAC list/watch | Watch + reconcile | P1 | read-only |
| Docker Swarm | Stacks, services, networks | Restricted inventory agent | Poll | P2 | read-only |
| ArgoCD | Applications, sync and rollouts | Read-only API token | Poll/events | P2 | read-only |
| Prometheus/OpenTelemetry | Metrics, traces, service graph | Read-only query token | Poll/queries | P3 | observed evidence |
| PostgreSQL/MySQL | Schemas, keys, tables, catalog metadata | Read-only catalog account | Poll | P1 | no rows by default |
| MongoDB | Collections and metadata | Read-only metadata principal | Poll | P2 | no records by default |
| Elasticsearch/OpenSearch | Mappings, aliases, indices | Read-only API token | Poll | P2 | no full-text by default |
| Neo4j/Qdrant | Graph/vector catalog metadata | Read-only account/API key | Poll | P3 | not authoritative |
| Kafka/Schema Registry | Topics, groups, schemas, offsets | Read-only metadata principal | Poll | P1 | no payload by default |
| S3/MinIO | Object metadata / selected docs | Read-only scoped token | Poll/events | P2 | explicit prefixes |
| OpenAPI URL | HTTP API contracts | Restricted endpoint URL | Poll | P1 | SSRF guard |
| Uploaded files | Docs/PDF/Word/slides/CSV | Authorized upload | Event after AV scan | P1 | Docling parser |
| AWS | Accounts, VPC, IAM-bound resource metadata, ECS/EKS, RDS topology | Cross-account read-only roles | Polling/config events | P3 | least-privilege |
| Azure | Subscriptions, AKS, App Service, network and database metadata | Managed identity / read-only service principal | Resource Graph/eventing | P3 | read-only |
| GCP | Projects, GKE, Cloud Run, networking and data resources | Scoped service account | Asset inventory/poll | P3 | read-only |
| Terraform/OpenTofu | IaC planned/declared topology | Git repository read | Commit-driven | P2 | source only |
| Helm/Kustomize | Deploy intent, values, overlays | Git repository read | Commit-driven | P2 | source only |
| Harbor / OCI registries | Image repositories, provenance and digest | Read-only robot account | Poll/webhook | P3 | no image push |
| Vault / secret managers | Secret *metadata* and application dependency metadata | Restricted metadata-only token | Poll | P3 | never reveal secret values |
| Grafana | Dashboards and service metadata | Read-only token | Poll | P3 | avoid raw restricted panels |
| Jenkins / CI | Builds, artifact provenance, deployment evidence | Read-only API token | Webhook/poll | P2 | no job execution |
| SharePoint / OneDrive | Architecture docs and governance artifacts | Scoped OAuth and user consent | Delta poll | P3 | docs only |
| Slack / Microsoft Teams | Drift/approval notifications and audit references | Scoped bot/installation | Outbound event | P3 | no sensitive payload by default |

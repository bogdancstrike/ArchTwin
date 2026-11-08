# Feature flag registry — implementation contract

This catalog is normative for module flags. Default enablement is `false` for all optional modules/providers. The five security invariants are unconditionally enabled, not bypassable flags. `security.emergency_kill_switch` **turns optional functionality off**; it cannot disable security.

| Flag | Default | Phase | Scope | Enforcement |
|---|---|---|---|---|
| `module.organizations` | `false` | phase-01-foundation | project | OFF until phase accepted |
| `module.project-boundaries` | `false` | phase-01-foundation | project | OFF until phase accepted |
| `module.identity-policy` | `false` | phase-01-foundation | project | OFF until phase accepted |
| `module.feature-flags` | `false` | phase-01-foundation | project | OFF until phase accepted |
| `module.audit-provenance` | `false` | phase-01-foundation | project | OFF until phase accepted |
| `module.canonical-events` | `false` | phase-01-foundation | project | OFF until phase accepted |
| `module.ui-workspaces` | `false` | phase-01-foundation | project | OFF until phase accepted |
| `module.llm-gateway` | `false` | phase-01-foundation | project | OFF until phase accepted |
| `module.connector-platform` | `false` | phase-02-connectors | project | OFF until phase accepted |
| `module.source-code-discovery` | `false` | phase-02-connectors | project | OFF until phase accepted |
| `module.runtime-discovery` | `false` | phase-02-connectors | project | OFF until phase accepted |
| `module.data-topology` | `false` | phase-02-connectors | project | OFF until phase accepted |
| `module.work-connectors` | `false` | phase-02-connectors | project | OFF until phase accepted |
| `module.document-parsing` | `false` | phase-02-connectors | project | OFF until phase accepted |
| `module.normalization-freshness` | `false` | phase-02-connectors | project | OFF until phase accepted |
| `module.architecture-graph` | `false` | phase-03-architecture | project | OFF until phase accepted |
| `module.diagram-studio` | `false` | phase-03-architecture | project | OFF until phase accepted |
| `module.documentation-engine` | `false` | phase-03-architecture | project | OFF until phase accepted |
| `module.adr-workflow` | `false` | phase-03-architecture | project | OFF until phase accepted |
| `module.architecture-reviews` | `false` | phase-03-architecture | project | OFF until phase accepted |
| `module.drift-engine` | `false` | phase-04-drift | project | OFF until phase accepted |
| `module.continuous-watchers` | `false` | phase-04-drift | project | OFF until phase accepted |
| `module.drift-triage` | `false` | phase-04-drift | project | OFF until phase accepted |
| `module.architecture-notifications` | `false` | phase-04-drift | project | OFF until phase accepted |
| `module.architecture-planning` | `false` | phase-05-delivery | project | OFF until phase accepted |
| `module.issue-synchronization` | `false` | phase-05-delivery | project | OFF until phase accepted |
| `module.implementation-traceability` | `false` | phase-05-delivery | project | OFF until phase accepted |
| `module.release-gates` | `false` | phase-05-delivery | project | OFF until phase accepted |
| `module.architecture-assistant` | `false` | phase-06-intelligence | project | OFF until phase accepted |
| `module.cross-project-federation` | `false` | phase-06-intelligence | project | OFF until phase accepted |
| `module.integration-designer` | `false` | phase-06-intelligence | project | OFF until phase accepted |
| `module.impact-analysis` | `false` | phase-06-intelligence | project | OFF until phase accepted |
| `module.ai-evaluations` | `false` | phase-06-intelligence | project | OFF until phase accepted |
| `module.enterprise-operations` | `false` | phase-07-enterprise | project | OFF until phase accepted |
| `module.collaboration-approvals` | `false` | phase-07-enterprise | project | OFF until phase accepted |
| `module.unified-search-export` | `false` | phase-07-enterprise | project | OFF until phase accepted |
| `module.connector-sdk` | `false` | phase-07-enterprise | project | OFF until phase accepted |
| `module.architecture-health` | `false` | phase-07-enterprise | project | OFF until phase accepted |
| `connector.github` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.gitlab` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.jira` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.taiga` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.bitbucket` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.azure_devops` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.confluence` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.notion` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.backstage` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.kubernetes` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.docker_swarm` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.argocd` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.prometheus` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.opentelemetry` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.postgresql` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.mysql` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.mongodb` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.elasticsearch` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.opensearch` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.neo4j` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.qdrant` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.kafka` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.s3` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.http_openapi` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `connector.file_upload` | `false` | phase-02-connectors | org/project | read-only by default; rollout approved |
| `ai.answers` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `ai.adr_drafting` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `ai.diagram_drafting` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `ai.integration_design` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `ai.task_drafting` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `ai.model_evaluation` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `ai.external_data_allowed` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `ai.prompt_content_tracing` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `connectors.webhooks` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `connectors.full_reconciliation` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `connectors.writeback.jira` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `connectors.writeback.taiga` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `connectors.writeback.github` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `connectors.writeback.gitlab` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `drift.blocking_ci` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `drift.email_alerts` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `drift.external_webhook_alerts` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `projects.federation` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `architecture.neo4j_projection` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `search.qdrant_projection` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `docs.pdf_export` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `docs.docx_export` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `docs.git_pr_publish` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `ui.portfolio` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `ui.executive_dashboard` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `security.emergency_kill_switch` | `false` | phase-specific | org/project | sensitive/optional; explicit enable |
| `security.oidc_required` | `true` | phase-01-foundation | immutable-security | cannot be disabled, including via emergency flags |
| `security.cerbos_required` | `true` | phase-01-foundation | immutable-security | cannot be disabled, including via emergency flags |
| `security.audit_required` | `true` | phase-01-foundation | immutable-security | cannot be disabled, including via emergency flags |
| `security.secret_encryption_required` | `true` | phase-01-foundation | immutable-security | cannot be disabled, including via emergency flags |
| `security.project_isolation_required` | `true` | phase-01-foundation | immutable-security | cannot be disabled, including via emergency flags |
| `connector.aws` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.azure` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.gcp` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.terraform` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.opentofu` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.helm` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.kustomize` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.harbor` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.vault_metadata` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.grafana` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.jenkins` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.sharepoint` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.onedrive` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.slack` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |
| `connector.teams` | `false` | phase-07-enterprise | org/project | optional adapter; read-only/notification-specific scopes |

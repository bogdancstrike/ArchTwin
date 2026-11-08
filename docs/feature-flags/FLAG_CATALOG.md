# Feature flag registry — implementation contract

This catalog is normative. The typed runtime catalog (`flags/catalog.yaml`) is generated from it, and CI fails when code references an unregistered key.

## Rules
- **Core platform modules are not flags.** Organizations, projects, identity/authorization, feature flags, audit, the data model/outbox and the UI shell are always on — a flag that can switch off authorization or audit is a vulnerability, not a feature.
- **Security invariants** (`security.*_required`) are hard-coded ON; any attempt to change them is rejected and audited.
- Optional modules and providers default to `false` and are enabled per org/project/environment once their phase exit gates pass.
- `security.emergency_kill_switch` turns optional functionality OFF; it can never disable security.
- Evaluation precedence: emergency-off > org policy > project/environment override > role cohort > default (see `README.md`).

## Model selection is not a flag
Which chat model a user may pick (`gpt-6-luna` default, `gpt-6-terra`, `gpt-6-sol`) is model policy in `docs/ai/MODEL_PROFILES.yaml` (org/project allowlists), not a feature flag.

| Flag | Default | Introduced in | Scope | Enforcement |
|---|---|---|---|---|
| `module.llm-gateway` | `false` | phase-01-foundation | org | admin diagnostics only until phase 06 |
| `module.connector-platform` | `false` | phase-02-connectors | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.source-code-discovery` | `false` | phase-02-connectors | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.runtime-discovery` | `false` | phase-02-connectors | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.data-topology` | `false` | phase-02-connectors | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.work-connectors` | `false` | phase-02-connectors | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.document-parsing` | `false` | phase-02-connectors | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.normalization-freshness` | `false` | phase-02-connectors | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.architecture-graph` | `false` | phase-03-architecture | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.diagram-studio` | `false` | phase-03-architecture | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.documentation-engine` | `false` | phase-03-architecture | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.adr-workflow` | `false` | phase-03-architecture | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.architecture-reviews` | `false` | phase-03-architecture | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.drift-engine` | `false` | phase-04-drift | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.continuous-watchers` | `false` | phase-04-drift | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.drift-triage` | `false` | phase-04-drift | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.architecture-notifications` | `false` | phase-04-drift | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.architecture-planning` | `false` | phase-05-delivery | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.issue-synchronization` | `false` | phase-05-delivery | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.implementation-traceability` | `false` | phase-05-delivery | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.release-gates` | `false` | phase-05-delivery | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.architecture-assistant` | `false` | phase-06-intelligence | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.cross-project-federation` | `false` | phase-06-intelligence | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.integration-designer` | `false` | phase-06-intelligence | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.impact-analysis` | `false` | phase-06-intelligence | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.ai-evaluations` | `false` | phase-06-intelligence | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.enterprise-operations` | `false` | phase-07-enterprise | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.collaboration-approvals` | `false` | phase-07-enterprise | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.unified-search-export` | `false` | phase-07-enterprise | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.connector-sdk` | `false` | phase-07-enterprise | project | OFF until phase exit gates pass; enabled per pilot project |
| `module.architecture-health` | `false` | phase-07-enterprise | project | OFF until phase exit gates pass; enabled per pilot project |
| `connector.github` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.gitlab` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.jira` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.taiga` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.bitbucket` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.azure_devops` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.confluence` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.notion` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.backstage` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.kubernetes` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.docker_swarm` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.argocd` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.prometheus` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.opentelemetry` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.postgresql` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.mysql` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.mongodb` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.elasticsearch` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.opensearch` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.neo4j` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.qdrant` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.kafka` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.s3` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.http_openapi` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.file_upload` | `false` | phase-02-connectors | org/project | read-only scopes; org security admin approves scopes and egress |
| `ai.answers` | `false` | phase-06-intelligence | org/project | explicit enable; eval thresholds must pass |
| `ai.adr_drafting` | `false` | phase-06-intelligence | org/project | explicit enable; eval thresholds must pass |
| `ai.diagram_drafting` | `false` | phase-06-intelligence | org/project | explicit enable; eval thresholds must pass |
| `ai.integration_design` | `false` | phase-06-intelligence | org/project | explicit enable; eval thresholds must pass |
| `ai.task_drafting` | `false` | phase-06-intelligence | org/project | explicit enable; eval thresholds must pass |
| `ai.model_evaluation` | `false` | phase-06-intelligence | org/project | explicit enable; eval thresholds must pass |
| `ai.external_data_allowed` | `false` | phase-06-intelligence | org/project | explicit enable; eval thresholds must pass |
| `ai.prompt_content_tracing` | `false` | phase-06-intelligence | org/project | explicit enable; eval thresholds must pass |
| `connectors.webhooks` | `false` | phase-02-connectors | org/project | explicit enable |
| `connectors.full_reconciliation` | `false` | phase-02-connectors | org/project | explicit enable |
| `connectors.writeback.jira` | `false` | phase-05-delivery | org/project | also requires Cerbos write_external + preview + explicit approval |
| `connectors.writeback.taiga` | `false` | phase-05-delivery | org/project | also requires Cerbos write_external + preview + explicit approval |
| `connectors.writeback.github` | `false` | phase-05-delivery | org/project | also requires Cerbos write_external + preview + explicit approval |
| `connectors.writeback.gitlab` | `false` | phase-05-delivery | org/project | also requires Cerbos write_external + preview + explicit approval |
| `drift.blocking_ci` | `false` | phase-05-delivery | org/project | explicit enable |
| `drift.email_alerts` | `false` | phase-04-drift | org/project | explicit enable |
| `drift.external_webhook_alerts` | `false` | phase-04-drift | org/project | explicit enable |
| `projects.federation` | `false` | phase-06-intelligence | org/project | explicit enable |
| `architecture.neo4j_projection` | `false` | phase-07-enterprise | org/project | explicit enable |
| `search.qdrant_projection` | `false` | phase-07-enterprise | org/project | explicit enable |
| `docs.pdf_export` | `false` | phase-03-architecture | org/project | explicit enable |
| `docs.docx_export` | `false` | phase-03-architecture | org/project | explicit enable |
| `docs.git_pr_publish` | `false` | phase-03-architecture | org/project | explicit enable |
| `ui.portfolio` | `false` | phase-07-enterprise | org/project | explicit enable |
| `ui.executive_dashboard` | `false` | phase-07-enterprise | org/project | explicit enable |
| `security.emergency_kill_switch` | `false` | phase-01-foundation | global/org/project | turns optional functionality OFF; cannot disable security invariants |
| `security.oidc_required` | `true` | phase-01-foundation | immutable-security | cannot be disabled, including via emergency flags |
| `security.cerbos_required` | `true` | phase-01-foundation | immutable-security | cannot be disabled, including via emergency flags |
| `security.audit_required` | `true` | phase-01-foundation | immutable-security | cannot be disabled, including via emergency flags |
| `security.secret_encryption_required` | `true` | phase-01-foundation | immutable-security | cannot be disabled, including via emergency flags |
| `security.project_isolation_required` | `true` | phase-01-foundation | immutable-security | cannot be disabled, including via emergency flags |
| `connector.aws` | `false` | phase-07-enterprise | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.azure` | `false` | phase-07-enterprise | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.gcp` | `false` | phase-07-enterprise | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.terraform` | `false` | phase-02-connectors (wave 2) | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.opentofu` | `false` | phase-02-connectors (wave 2) | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.helm` | `false` | phase-02-connectors (wave 2) | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.kustomize` | `false` | phase-02-connectors (wave 2) | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.harbor` | `false` | phase-07-enterprise | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.vault_metadata` | `false` | phase-07-enterprise | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.grafana` | `false` | phase-07-enterprise | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.jenkins` | `false` | phase-02-connectors (wave 2) | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.sharepoint` | `false` | phase-07-enterprise | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.onedrive` | `false` | phase-07-enterprise | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.slack` | `false` | phase-07-enterprise | org/project | read-only scopes; org security admin approves scopes and egress |
| `connector.teams` | `false` | phase-07-enterprise | org/project | read-only scopes; org security admin approves scopes and egress |

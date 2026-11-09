# Specifications index

All capability specs are **ADDED** deltas for greenfield phases. `openspec/specs/` stays empty until a phase is implemented and archived. Every requirement has a positive and a negative/edge-case scenario.

Regenerate this table and `acceptance/REQUIREMENT_TRACEABILITY.csv` from the specs whenever requirements change.

| Phase | Capability | Requirements | Scenarios | Spec |
|---|---|---:|---:|---|
| phase-01-foundation | Auditability and evidence provenance | 3 | 6 | [`audit-provenance`](../openspec/changes/phase-01-foundation/specs/audit-provenance/spec.md) |
| phase-01-foundation | Persistent data model and domain events | 3 | 6 | [`canonical-events`](../openspec/changes/phase-01-foundation/specs/canonical-events/spec.md) |
| phase-01-foundation | Feature flags and kill switches | 3 | 6 | [`feature-flags`](../openspec/changes/phase-01-foundation/specs/feature-flags/spec.md) |
| phase-01-foundation | Identity, Cerbos authorization and secrets | 5 | 10 | [`identity-policy`](../openspec/changes/phase-01-foundation/specs/identity-policy/spec.md) |
| phase-01-foundation | LiteLLM, Langfuse and AI provider abstraction | 5 | 10 | [`llm-gateway`](../openspec/changes/phase-01-foundation/specs/llm-gateway/spec.md) |
| phase-01-foundation | Organizations and governance | 3 | 6 | [`organizations`](../openspec/changes/phase-01-foundation/specs/organizations/spec.md) |
| phase-01-foundation | Projects and bounded architecture scope | 4 | 8 | [`project-boundaries`](../openspec/changes/phase-01-foundation/specs/project-boundaries/spec.md) |
| phase-01-foundation | Architect-first UX and workspaces | 3 | 6 | [`ui-workspaces`](../openspec/changes/phase-01-foundation/specs/ui-workspaces/spec.md) |
| phase-02-connectors | Secure connector lifecycle and ingestion SDK | 3 | 6 | [`connector-platform`](../openspec/changes/phase-02-connectors/specs/connector-platform/spec.md) |
| phase-02-connectors | Database and messaging topology discovery | 3 | 6 | [`data-topology`](../openspec/changes/phase-02-connectors/specs/data-topology/spec.md) |
| phase-02-connectors | Document and diagram import processing | 3 | 6 | [`document-parsing`](../openspec/changes/phase-02-connectors/specs/document-parsing/spec.md) |
| phase-02-connectors | Evidence normalization, confidence and freshness | 3 | 6 | [`normalization-freshness`](../openspec/changes/phase-02-connectors/specs/normalization-freshness/spec.md) |
| phase-02-connectors | Runtime infrastructure inventory | 3 | 6 | [`runtime-discovery`](../openspec/changes/phase-02-connectors/specs/runtime-discovery/spec.md) |
| phase-02-connectors | Source repository and code architecture extraction | 5 | 10 | [`source-code-discovery`](../openspec/changes/phase-02-connectors/specs/source-code-discovery/spec.md) |
| phase-02-connectors | GitHub/GitLab, Jira and Taiga application connectors | 3 | 6 | [`work-connectors`](../openspec/changes/phase-02-connectors/specs/work-connectors/spec.md) |
| phase-03-architecture | Architecture decisions and review governance | 3 | 6 | [`adr-workflow`](../openspec/changes/phase-03-architecture/specs/adr-workflow/spec.md) |
| phase-03-architecture | Canonical architectural knowledge graph | 3 | 6 | [`architecture-graph`](../openspec/changes/phase-03-architecture/specs/architecture-graph/spec.md) |
| phase-03-architecture | Architecture quality assessments | 3 | 6 | [`architecture-reviews`](../openspec/changes/phase-03-architecture/specs/architecture-reviews/spec.md) |
| phase-03-architecture | Diagram generation and visual architecture editing | 7 | 14 | [`diagram-studio`](../openspec/changes/phase-03-architecture/specs/diagram-studio/spec.md) |
| phase-03-architecture | Living architecture documentation | 3 | 6 | [`documentation-engine`](../openspec/changes/phase-03-architecture/specs/documentation-engine/spec.md) |
| phase-04-drift | Architecture alerts and digests | 3 | 6 | [`architecture-notifications`](../openspec/changes/phase-04-drift/specs/architecture-notifications/spec.md) |
| phase-04-drift | Near-real-time watchers and reconciliation | 3 | 6 | [`continuous-watchers`](../openspec/changes/phase-04-drift/specs/continuous-watchers/spec.md) |
| phase-04-drift | Desired, observed and implemented architecture drift | 4 | 8 | [`drift-engine`](../openspec/changes/phase-04-drift/specs/drift-engine/spec.md) |
| phase-04-drift | Drift scoring and lifecycle | 3 | 6 | [`drift-triage`](../openspec/changes/phase-04-drift/specs/drift-triage/spec.md) |
| phase-05-delivery | Roadmaps, plans and architecture increments | 3 | 6 | [`architecture-planning`](../openspec/changes/phase-05-delivery/specs/architecture-planning/spec.md) |
| phase-05-delivery | Implementation evidence and delivery tracking | 3 | 6 | [`implementation-traceability`](../openspec/changes/phase-05-delivery/specs/implementation-traceability/spec.md) |
| phase-05-delivery | Taiga, Jira, GitLab and GitHub work tracking | 3 | 6 | [`issue-synchronization`](../openspec/changes/phase-05-delivery/specs/issue-synchronization/spec.md) |
| phase-05-delivery | Architecture-aware release checks | 3 | 6 | [`release-gates`](../openspec/changes/phase-05-delivery/specs/release-gates/spec.md) |
| phase-06-intelligence | AI quality, security and model flexibility | 3 | 6 | [`ai-evaluations`](../openspec/changes/phase-06-intelligence/specs/ai-evaluations/spec.md) |
| phase-06-intelligence | Grounded AI architecture copilot | 4 | 8 | [`architecture-assistant`](../openspec/changes/phase-06-intelligence/specs/architecture-assistant/spec.md) |
| phase-06-intelligence | Project federation and cross-platform graph | 3 | 6 | [`cross-project-federation`](../openspec/changes/phase-06-intelligence/specs/cross-project-federation/spec.md) |
| phase-06-intelligence | What-if simulation and blast-radius analysis | 3 | 6 | [`impact-analysis`](../openspec/changes/phase-06-intelligence/specs/impact-analysis/spec.md) |
| phase-06-intelligence | Cross-platform integration design assistant | 3 | 6 | [`integration-designer`](../openspec/changes/phase-06-intelligence/specs/integration-designer/spec.md) |
| phase-07-enterprise | Architecture health and portfolio insights | 3 | 6 | [`architecture-health`](../openspec/changes/phase-07-enterprise/specs/architecture-health/spec.md) |
| phase-07-enterprise | Multi-user collaboration, comments and approvals | 3 | 6 | [`collaboration-approvals`](../openspec/changes/phase-07-enterprise/specs/collaboration-approvals/spec.md) |
| phase-07-enterprise | Extension SDK and connector marketplace model | 3 | 6 | [`connector-sdk`](../openspec/changes/phase-07-enterprise/specs/connector-sdk/spec.md) |
| phase-07-enterprise | Reliability, scale, backup and retention | 3 | 6 | [`enterprise-operations`](../openspec/changes/phase-07-enterprise/specs/enterprise-operations/spec.md) |
| phase-07-enterprise | Unified search, discovery and portability | 3 | 6 | [`unified-search-export`](../openspec/changes/phase-07-enterprise/specs/unified-search-export/spec.md) |

**Total: 38 capability specs / 127 requirements / 254 scenarios.**

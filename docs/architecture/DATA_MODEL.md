# Data model, invariants and graph taxonomy

## Identity and ownership
`org_id → project_id → environment_id`. Every asset, evidence, connector, task, model snapshot, flag override and alert has explicit ownership; public/portfolio reference objects are shared **by grant**, not by stripping scope.

## Canonical entities (logical schema)
| Entity | Key attributes / important relations |
|---|---|
| Organization | id, owner, retention, org policy |
| Project | org_id, slug, scope, purpose, tags, owner, lifecycle |
| Environment | project_id, name, criticality, network zone, baselines |
| SourceConnection | provider, credential_ref, permissions, freshness SLA, last cursor |
| SourceArtifact | raw hash, object URI, provider object key, observed_at, parser version, label |
| Observation | subject/source ID, version, evidence span, confidence, kind (desired/static/runtime/manual/issue/inferred) |
| ArchitectureNode | stable canonical ID, type, owner, project, environment, business role, validity |
| ArchitectureEdge | src, dst, relation type, direction, contract, validity, trust boundary, evidence |
| ArchitectureSnapshot | version, manifest hash, environment, materialized graph refs, baseline status |
| DiagramView | graph snapshot, query/filter, layout overrides, view type, review status |
| DocumentVersion | format, source refs, claims, published_at, reviewer |
| ADR | accepted immutable version, alternatives, consequences, affected nodes |
| Initiative/Milestone/Task | plan hierarchy and work tracker links; separately verified evidence |
| DriftFinding | rule_version, expected/actual refs, severity, lifecycle, suppression expiry |
| FederationGrant | source project, target project, relation/data-class scope, expiry, policy approval |
| PromptRun | model alias, Langfuse trace, budgets, project/data scope, source references |
| AuditEvent | append-only action, principal, policy decision, correlation and chain digest |

## Graph node types
`org`, `project`, `software-system`, `external-system`, `container`, `component`, `service`, `library`, `api-endpoint`, `api-contract`, `event-schema`, `kafka-topic`, `consumer-group`, `database`, `db-schema`, `table`, `index`, `deployment`, `workload`, `network-zone`, `team`, `person-role`, `requirement`, `adr`, `initiative`, `work-item`, `source-artifact`, `runtime-observation`.

## Edge types
`contains`, `depends-on`, `calls`, `publishes`, `consumes`, `reads`, `writes`, `deploys-as`, `hosted-on`, `exposes`, `authenticated-by`, `authorized-by`, `owned-by`, `implements`, `tests`, `decided-by`, `tracked-by`, `derived-from`, `conflicts-with`, `supersedes`, `integrates-with`.

All edges support provenance, environment, detection method, evidence confidence, time-range, contract reference, risk labels and declared/observed/inferred status. Do not expose an inferred relationship as established.

## Example PostgreSQL DDL — conceptual only
```sql
CREATE TABLE organizations (
 id uuid PRIMARY KEY, name text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE projects (
 id uuid PRIMARY KEY, org_id uuid NOT NULL REFERENCES organizations(id),
 slug text NOT NULL, title text NOT NULL, purpose text, scope jsonb NOT NULL DEFAULT '{}'::jsonb,
 status text NOT NULL DEFAULT 'active', created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(org_id,slug), UNIQUE(org_id,id)
);
CREATE TABLE environments (
 id uuid PRIMARY KEY, org_id uuid NOT NULL, project_id uuid NOT NULL,
 name text NOT NULL, criticality text NOT NULL DEFAULT 'normal',
 FOREIGN KEY(org_id,project_id) REFERENCES projects(org_id,id), UNIQUE(project_id,name)
);
CREATE TABLE architecture_nodes (
 id uuid PRIMARY KEY, org_id uuid NOT NULL, project_id uuid NOT NULL,
 logical_key text NOT NULL, kind text NOT NULL, attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
 valid_from timestamptz NOT NULL, valid_to timestamptz,
 FOREIGN KEY(org_id,project_id) REFERENCES projects(org_id,id)
);
CREATE TABLE architecture_edges (
 id uuid PRIMARY KEY, org_id uuid NOT NULL, project_id uuid NOT NULL,
 source_id uuid NOT NULL REFERENCES architecture_nodes(id),
 target_id uuid NOT NULL REFERENCES architecture_nodes(id),
 relation_kind text NOT NULL, origin_kind text NOT NULL,
 valid_from timestamptz NOT NULL, valid_to timestamptz,
 confidence numeric(4,3), evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
 FOREIGN KEY(org_id,project_id) REFERENCES projects(org_id,id)
);
CREATE TABLE outbox_events (
 id uuid PRIMARY KEY, org_id uuid NOT NULL, project_id uuid,
 aggregate_kind text NOT NULL, aggregate_id uuid NOT NULL, event_kind text NOT NULL,
 payload jsonb NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now(), delivered_at timestamptz
);
```

Production migrations additionally MUST enforce child ownership of both endpoint nodes (e.g., composite keys/validated triggers), avoid graph-edge cross-project FK ambiguity, implement indexed time-range queries, append-only evidence, encryption references, partitioning and tested RLS policy behavior. The above DDL is **illustrative**, not sufficient for deployment.

## RLS and authorization
Use PostgreSQL RLS only as defense in depth. Tenant context is established from a verified API principal; DB roles, pool session lifecycle and transaction-local context MUST prevent stale context reuse. Cerbos authorizes before access; SQL filters and per-record checks enforce approved scopes. Never trust a client-supplied `org_id`, `project_id` or arbitrary SQL `SET` as an identity assertion. All search indexes/projections carry stable scoped ACL fields and must deny if stale permissions cannot be safely evaluated.

## Retention and temporal behavior
- Source observations immutable; logical supersession by validity range/tombstone, never destructive rewriting of historical evidence.
- Diagrams bind graph snapshot and layout version. Snapshot hash stored in export manifest.
- Project deletion must revoke connectors, stop workloads, honor legal holds and scrub caches and embedding projections before reporting completion.
- All capture times UTC, source timestamps preserved with original timezone metadata when provided.

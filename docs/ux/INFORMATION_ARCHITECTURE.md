# Architect Studio — UI information architecture

## Main navigation
**Portfolio** (gated) · **Projects** · **Architecture Studio** · **Observability/Drift** · **Plans & Delivery** · **Decisions & Docs** · **Integration Designer** · **Assistant** · **Sources & Connectors** · **Administration**.

### Portfolio
Approved cross-project landscape, architecture health, top risks, dependency density, organization ADR policies and explicitly shared federation topology. Individual projects remain isolated by default.

### Project workspace
- Home: state summary, coverage/freshness, recent meaningful changes, project milestones, open risks and actions.
- Overview: scope, description, people, environments, source catalog and guardrails.
- Architecture: tabs `Current` / `Desired` / `Code` / `Runtime` / `Planned` / `Compare`, with C4 zoom selector and timeline slider.
- Diagrams: context, containers, components, deployment, data-flow, event-flow, sequence, freeform annotated canvas; fullscreen, search, layout locks, export.
- Architecture Explorer: graph catalog, relationships, ownership, source evidence, navigation and diagrams from selected nodes.
- Docs/ADRs: indexed docs with typed templates, review status and source-linked claims.
- Changes: chronological architecture evolution including code commits, deployments, baseline changes and detected drift.
- Drift: prioritized findings, evidence diff, rule, impact, reviewer, suppression and remediation task links.
- Plan: capability/milestone/initiative boards, architecture changes, external issue mapping, code/deployed verification states.
- Integrations: connection points, planned interfaces and design alternatives, explicit cross-project grants.
- Assistant: source-grounded chat scoped to selected project(s), environment, snapshot and evidence mode.
- Settings: member roles, connectors, model profiles, budgets, feature flags, retention and export.

## Important UX safeguards
- Persistent scope chip in every view: `[Org] / [Project] / [Environment] / [Snapshot time]`.
- Side-by-side three-way diff between **desired / code / runtime**; no unlabeled blending.
- Evidence inspector on diagram nodes/edges/AI citations: linked path/line, Git SHA, runtime resource UID, timestamps, freshness and policy visibility.
- Explicit visual distinction for proposed vs confirmed vs inferred vs stale states using more than color (icons, labels, legends).
- Applied diagrams require published baseline workflow; AI drafts never mutate baseline automatically.
- Project A ↔ B integration wizard requires source+target scopes and highlights federation grants.
- Disabled modules show reason (feature flag, missing license/connector, insufficient role) without revealing protected project names.
- WCAG 2.2 AA target, keyboard-accessible node details and table alternative for every graph view.

## Suggested frontend modules
`app-shell/`, `auth/`, `portfolio/`, `projects/`, `architecture/`, `diagrams/`, `evidence/`, `docs/`, `adrs/`, `drift/`, `planning/`, `connectors/`, `integration-designer/`, `assistant/`, `admin/`, `shared/ui/`.
Use shadcn/ui primitives with consistent density modes; React Flow for interactive topology and dedicated render/export adapters for Mermaid/Structurizr. Diagrams require long-list virtualization and graph sampling for large projects.

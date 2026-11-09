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

## Command palette (⌘K / Ctrl+K)
Available on every page from the keyboard or the "Search or jump to…" button in the top bar (`apps/web/src/components/command/`):
- **Go to**: every tab of the current project (Overview, Architecture, Flows, Drift, Decisions, Docs, Assistant, Datasources, Settings)
  and the global pages (Home, All projects, Usage & costs; System, Roles & permissions, Feature flags, Audit trail for org admins).
- **Search the current project** (live, debounced, ≥ 2 characters): architecture elements (open the diagram that draws the element,
  selected and centered via `?focus=`), recognized flows (`?flow=`), decision records (`?adr=`) and documents (`?doc=`).
- **Actions**: new project, add datasource, scan all datasources, evaluate drift, generate documentation, new ADR, toggle theme (⌘⇧L), sign out.
- **Switch project** (favorites first) and **Recent** destinations on an empty query.
- Fuzzy matching (cmdk), ↑/↓ to move, Enter to open, Esc to close. Deep-link parameters (`?new=1`, `?add=1`, `?flow=`, `?doc=`) are
  consumed once and removed from the URL.

## Themes
Light (diagram-design default skin) and **night**: neutral warm-graphite surfaces (`#141414` paper, `#1b1b1b` cards, `#232323` raised)
with no blue cast; every text token meets WCAG AA (≥ 4.5:1) on all three surfaces, chart series are re-validated on the dark surface,
and Mermaid diagrams, code highlighting, React Flow canvases (controls, minimap, markers) and toasts follow the theme.

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

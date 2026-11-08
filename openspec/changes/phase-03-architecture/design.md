# Design: Living diagrams and architecture knowledge

## Context
Implements `specs/` of this change. Graph semantics: `docs/architecture/DATA_MODEL.md`. ADR-0002 (PostgreSQL canonical graph) and ADR-0003 (evidence model) apply.

## Goals / Non-goals
- **Goals:** temporal graph in PostgreSQL, snapshots and approved baselines, C4 views, diff, docs with citations, ADR lifecycle, review checklists.
- **Non-goals:** a graph database as the source of truth, real-time collaborative editing (phase 07), AI-generated diagrams (phase 06).

## Model layers (never merged silently)
| Layer | Written by | Mutable? |
|---|---|---|
| Observations | connectors | append-only |
| Derived graph (static / runtime) | graph builder from observations | new version per build |
| Curated overlay (intent, boundaries, annotations) | architects, via reviewed commands | versioned |
| Baseline | approval of (derived + overlay) at a point in time | immutable |

## Decisions

| # | Decision | Adopted OSS | Notes |
|---|---|---|---|
| D1 | Graph = `architecture_nodes`/`architecture_edges` with `valid_from/valid_to`, `origin`, `confidence`, composite FKs to `(org_id, project_id)`; traversals via recursive CTEs with depth/node caps | PostgreSQL | Neo4j projection optional later (ADR-0002); rebuildable from Postgres |
| D2 | Snapshot = immutable manifest `{node_ids, edge_ids, versions}` + sha256; diff = set comparison on stable logical keys | — | Core domain logic; small and fully testable |
| D3 | Graph builder is a pure function `observations → graph version`, run by a Temporal workflow on `inventory.changed` (debounced) | Temporal | Deterministic ⇒ reproducible and replayable |
| D4 | In-memory algorithms (paths, components, centrality) on bounded subgraphs | networkx | No custom graph algorithm code |
| D5 | Diagram = view definition (query + filters + C4 level) + separate layout document (node positions, user overrides) | — | Regeneration keeps overrides; reset is explicit |
| D6 | Rendering/editing: React Flow; automatic layout: elkjs (layered) in a Web Worker; table view as accessible alternative | @xyflow/react, elkjs | Spike S4 validates 2k elements |
| D7 | Mermaid export generated server-side with escaping (interchange format only — Mermaid's renderer layout is **not** used for platform figures, per the design system's anti-patterns); client rendering with `securityLevel: 'strict'` only for imported user Mermaid | Mermaid | No HTML labels |
| D8 | Structurizr: export DSL from templates; import by running **Structurizr CLI** in a sandbox to convert DSL → workspace JSON, then map to our model with a user-assisted mapping step for ambiguous elements | Structurizr CLI | Never write our own DSL parser |
| D9 | ADRs follow **MADR**; accepted versions immutable; supersession explicit; export to `docs/adr/NNNN-*.md` (compatible with adr-tools/Log4brains) | MADR | — |
| D10 | Docs generation = deterministic Jinja2 templates over graph facts (every sentence carries evidence IDs); optional LLM narrative is added only in phase 06 and goes through the same citation check | Jinja2 | Coverage report: % claims with evidence |
| D11 | Export: Markdown native; DOCX via Pandoc; PDF via WeasyPrint in an isolated container with network disabled | Pandoc, WeasyPrint | Same as Horizon exports |
| D13 | **Editorial diagram design system.** Generated diagrams follow the open-source *diagram-design* skill (MIT, github.com/cathrynlavery/diagram-design). We vendor its design references (style guide tokens, type references, connector rules, anti-patterns) into `packages/diagram-design-system/` with attribution, and implement them as: (a) a **theme token set** per org (paper, ink, muted, accent, link, …) with the skill's brand-onboarding flow as an admin page; (b) a **type router** mapping ArchTwin views to skill visual types (C4 context/container → *Architecture*, deployment → *Deployment*, sequence → *Sequence*, data model → *ER / DB schema*, dependency/blast radius → *Dependency graph*, drift history → *Timeline*, roadmap → *Gantt*, risk register → *Quadrant*, access policy → *DP security matrix*, trust boundaries → *Secure paved road* pattern); (c) **node treatments** from element kind (focal, service, store, external, user, async, boundary); (d) a **focal selector** (≤2 accents: the selected/drifted/changed element); (e) a **complexity budget** (>9 primary nodes ⇒ overview + detail views); (f) **orthogonal routing** via elkjs (`edgeRouting: ORTHOGONAL`, port constraints for fanned attach points) plus a post-processor for rounded bends, label masks, gaps and hop bridges; (g) a **linter** implementing the skill's pre-output checklist (six connector rules + anti-patterns) run at render time and in CI on golden diagrams. Output: standalone SVG/HTML (and PNG via headless rendering) for docs and exports; the React Flow editor uses the same tokens and node components so edit and export look the same. AI-drafted diagrams (phase 06) receive the skill rules as instructions and pass the same linter | diagram-design (MIT), elkjs, Playwright (PNG) | Reusing a proven, documented design system avoids inventing visual rules; the linter makes them enforceable |
| D14 | **C4 zoom navigation** (L1 context → L2 container → L3 component). The graph's `contains` hierarchy drives a *semantic zoom*: zooming into a node (double-click, pinch/scroll past a threshold, `Enter` key, or "Zoom in" action) runs a shared-element transition — the selected node's box scales and morphs into the frame of the child view while siblings fade out and children fade/slide in (≈400 ms, ease-out), then the child view is laid out by elkjs and rendered with the same diagram-design tokens. Zoom-out reverses the motion; breadcrumbs (`Context › System › Container`) and browser history (URL `?level=&focus=`) allow direct navigation. Child layouts are prefetched on hover so the animation never waits for the network. Motion follows the diagram-design animation guidance (motion only to explain ordered change) and honours `prefers-reduced-motion` with an instant cross-fade. Implemented with React Flow viewport APIs (`setViewport`/`fitBounds` with duration) plus **Motion** (`motion/react`, layout animations) — the same library Horizon uses | React Flow, Motion, elkjs | No custom animation engine; levels without evidence show an explicit "no component-level evidence" state |
| D12 | Reviews: checklist packs as versioned YAML rules evaluated over the graph (e.g., SPOF = single replica on critical path, public ingress without auth annotation); results labelled automated vs manual | — | Simple rule DSL in YAML + Python predicates; no generic rules engine |

## Threat controls
Escaping for all labels; Cerbos checks on export with per-element filtering; renderer containers without network; baselines/ADR rows protected by triggers; separation of duties enforced in Cerbos (author ≠ approver).

## Risks / trade-offs
| Risk | Mitigation |
|---|---|
| Generated diagrams look cluttered → architects stop using them | C4 level filtering, aggregation of minor nodes, ELK layered layout, saved layouts; usability test with design partners at M1 |
| Identity merges wrong (two services merged) | Merge only on authoritative keys; suggestions queue; split command |
| Recursive CTE performance on large graphs | Indexed `(project_id, valid_to)`, depth/node caps, benchmark at 5k nodes/20k edges (NFR) |
| Structurizr import lossy | Explicit mapping review step and "dropped elements" report |

## Rollback
Module flags; baselines and ADRs are immutable; graph versions can be rebuilt from observations with an older builder version.

## Open questions
- Component-level (L3) evidence depends on code extraction quality (spike S2); zoom navigation ships L1→L2 in M1 and L3 for containers whose components are discovered or curated.

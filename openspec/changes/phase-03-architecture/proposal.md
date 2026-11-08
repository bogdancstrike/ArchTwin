# Proposal: Living diagrams and architecture knowledge

## Why
Observations alone are noise. Architects need one canonical, versioned model that merges evidence, separates *intent* from *observation*, and renders as C4 views they can edit, review and export. This phase turns phase-02 evidence into the architecture graph, baselines, diagrams, living documentation and ADRs — the first thing a design partner will judge ("is the generated model trustworthy enough to keep using?").

Users affected: architects (model, diagrams, ADRs), reviewers, engineers reading docs.

## What Changes
- Add **Canonical architectural knowledge graph** (`architecture-graph`).
- Add **Diagram generation and visual architecture editing** (`diagram-studio`).
- Add **Living architecture documentation** (`documentation-engine`).
- Add **Architecture decisions and review governance** (`adr-workflow`).
- Add **Architecture quality assessments** (`architecture-reviews`).

## Impact
- **Modules:** `architecture` (graph, snapshots, baselines, diff), `diagrams`, `documents` (generation), `decisions`, `reviews`.
- **Tables:** architecture_nodes, architecture_edges (temporal validity, origin, confidence), node_evidence/edge_evidence links, snapshots (manifest hash), baselines, diagram_views, diagram_layouts, doc_versions, adrs, adr_reviews, review_runs, risks.
- **APIs:** `/projects/{id}/architecture?at=&environment=`, `/snapshots/{id}/diff`, `/baselines`, `/diagrams`, `/adrs`, `/reviews`, export endpoints.
- **Adopted OSS:** diagram-design editorial design system (MIT; tokens, visual types, connector rules — vendored as `packages/diagram-design-system`), React Flow (`@xyflow/react`), elkjs (layout), Mermaid (render/export, strict security level), Structurizr CLI (DSL ⇄ workspace JSON, run in a sandboxed container), MADR template for ADRs, Jinja2 (deterministic doc templates), Pandoc (DOCX), WeasyPrint (PDF), networkx (bounded in-memory graph algorithms).
- **Flags:** `module.architecture-graph`, `module.diagram-studio`, `module.documentation-engine`, `module.adr-workflow`, `module.architecture-reviews`, `docs.pdf_export`, `docs.docx_export`, `docs.git_pr_publish`.

## Dependencies
Phases 01–02.

## Security risks
XSS through labels (Mermaid/HTML), export leaking restricted elements, renderer SSRF, scans overwriting approved intent.

## Rollout and rollback
Graph builds run in shadow mode first (computed, not shown) until fixture precision is acceptable; diagrams and docs ship behind module flags. Baselines are immutable, so rollback never loses approved intent.

## Success
- From the fixture, a C4 container diagram is generated with evidence on every element and edge; manual layout survives regeneration.
- Two snapshots can be diffed (added/removed/changed) with evidence for both sides.
- An ADR is proposed, independently approved, becomes immutable and is exported as MADR Markdown.
- Export to Structurizr DSL and Mermaid round-trips stable element IDs.

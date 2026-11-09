# Implementation tasks — phase-03-architecture

Legend: **[MVP]** required for M1 · **[Later]** may slip. Check a task only with merged code and green tests.

## 1. Architecture graph — AT-ARCHITECTURE_GRAPH-001..003
- [x] 1.1 [MVP] Node/edge tables with temporal validity, origin, confidence, evidence links, composite FKs; RLS.
- [x] 1.2 [MVP] Deterministic graph builder (pure function + Temporal workflow, debounced on `inventory.changed`); golden tests on fixture observations.
- [x] 1.3 [MVP] Identity reconciliation on authoritative keys + suggestion queue + merge/split commands (audited).
- [x] 1.4 [MVP] Snapshots with manifest hash; `GET architecture?at=` time travel; snapshot diff API.
- [x] 1.5 [MVP] Curated overlay + baseline approval (Cerbos: author ≠ approver); scans cannot mutate baselines (test).

## 2. Diagram studio — AT-DIAGRAM_STUDIO-001..007
- [x] 2.1 [MVP] C4 context + container views from view definitions; React Flow canvas; elkjs layout in a Web Worker.
- [x] 2.2 [MVP] Layout persistence with overrides; regenerate keeps overrides; explicit reset.
- [x] 2.3 [MVP] Evidence side panel on every node/edge (source, revision, observed_at, confidence, freshness).
- [x] 2.4 [MVP] Snapshot comparison view (added/removed/changed highlighting).
- [x] 2.5 [MVP] Mermaid + Structurizr DSL export with escaping tests (XSS corpus).
- [ ] 2.6 [Later] Structurizr DSL import via sandboxed Structurizr CLI + mapping review.
- [ ] 2.7 [Later] Deployment, data-flow, event-flow, sequence views; component level.
- [x] 2.9 [MVP] `packages/diagram-design-system`: vendor diagram-design references (MIT, attribution in THIRD_PARTY_NOTICES), token schema + default skin, node treatments, type router for Architecture/Deployment/Dependency views — AT-DIAGRAM_STUDIO-005.
- [x] 2.10 [MVP] Orthogonal routing (elkjs ORTHOGONAL + port fanning) + post-processor (rounded bends, label masks with 6–10 px gap, hop bridges); focal selector; >9-node overview/detail split.
- [ ] 2.11 [MVP] Diagram linter (six connector rules + anti-pattern checks; AT-DIAGRAM_STUDIO-006) at render/export time and in CI over golden fixture diagrams; standalone SVG/HTML export, PNG via headless Chromium.
- [ ] 2.12 [Later] Org brand onboarding page (tokens from URL/manual, per the skill's onboarding flow); Sequence, ER/DB schema, Timeline, Gantt, Quadrant types.
- [x] 2.13 [MVP] C4 zoom navigation L1→L2 (AT-DIAGRAM_STUDIO-007): shared-element zoom animation (React Flow viewport + Motion), breadcrumbs, URL state, keyboard (`Enter`/`Backspace`), hover prefetch, reduced-motion cross-fade; Playwright test of the full path.
- [ ] 2.14 [Later] L2→L3 component zoom once component extraction/curation exists; "no component-level evidence" empty state.
- [ ] 2.8 [MVP] Accessible table view; keyboard navigation; 2k-element performance check (spike S4 numbers).

## 3. ADR workflow — AT-ADR_WORKFLOW-001..003
- [x] 3.1 [MVP] MADR-based ADR model, states proposed/accepted/rejected/superseded, immutable accepted versions.
- [x] 3.2 [MVP] Links to nodes/edges/requirements; independent approval policy in Cerbos.
- [x] 3.3 [Later] ADR conformance hints (decision vs observed edges) — full version arrives with drift (phase 04).

## 4. Documentation engine — AT-DOCUMENTATION_ENGINE-001..003
- [x] 4.1 [MVP] Jinja2 templates: system overview, container catalog, interface catalog; every generated sentence carries evidence IDs; coverage report.
- [x] 4.2 [MVP] Regeneration produces a reviewable diff; hand-edited sections protected.
- [x] 4.3 [MVP] Markdown export with permission filtering.
- [ ] 4.4 [Later] PDF (WeasyPrint) and DOCX (Pandoc) in isolated containers; Git PR publish behind `docs.git_pr_publish`.

## 5. Architecture reviews — AT-ARCHITECTURE_REVIEWS-001..003
- [ ] 5.1 [Later] YAML checklist packs (reliability, security first) with Python predicates; automated vs manual results; "not evaluated" when inputs are missing.
- [ ] 5.2 [Later] Risk register with owner, evidence, expiry of acceptance.

## X. Phase exit gates
- [ ] X.1 Fixture demo: generated C4 container diagram, evidence on every element, manual layout survives regeneration, diff between two commits.
- [ ] X.2 XSS/export-leak suites green; baseline immutability tests green.
- [ ] X.3 Graph query p95 and diagram render time recorded against `docs/acceptance/NFR_SLOS.md`.
- [ ] X.4 Design-partner usability session held; findings recorded (go/no-go input for M1).

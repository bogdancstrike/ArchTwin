# Diagrams

Every diagram in this repository is drawn with the open-source [diagram-design](https://github.com/cathrynlavery/diagram-design) system (MIT), default skin — which is also the ArchTwin palette (`.diagram-design` → `profile: default`). The platform uses the same system for the diagrams it generates (ADR-0009, `AT-DIAGRAM_STUDIO-005/006`).

| Diagram | Type | Files |
|---|---|---|
| How ArchTwin works | Architecture | [png](how-it-works.png) · [svg](how-it-works.svg) · [html](how-it-works.html) |
| System context (C4 L1) | Architecture | [png](system-context.png) · [svg](system-context.svg) · [html](system-context.html) |
| Containers (C4 L2) | Architecture | [png](containers.png) · [svg](containers.svg) · [html](containers.html) |
| Drift detection | Sequence | [png](drift-sequence.png) · [svg](drift-sequence.svg) · [html](drift-sequence.html) |
| Grounded cross-platform design | Sequence | [png](ai-design-sequence.png) · [svg](ai-design-sequence.svg) · [html](ai-design-sequence.html) |
| Delivery milestones | Gantt | [png](milestones.png) · [svg](milestones.svg) · [html](milestones.html) |

The HTML files are the source of truth (self-contained, accessible SVG). PNGs are used in Markdown because GitHub does not load web fonts inside SVG images.

## Rebuild
```bash
python3 docs/diagrams/build_diagrams.py          # regenerate HTML (all coordinates on the 4px grid)
node docs/diagrams/export_diagrams.mjs           # export SVG + 2x PNG (needs the `playwright` npm package + Chromium)
```
Do not add Mermaid diagrams to the docs; add a diagram here instead. Check new diagrams with the diagram-design self-check (`scripts/self_check.py`) and its pre-output checklist.

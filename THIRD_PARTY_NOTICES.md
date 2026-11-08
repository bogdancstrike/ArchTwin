# Third-party notices

ArchTwin adopts (does not fork) the open-source components listed in [`docs/TECHNOLOGIES.md`](docs/TECHNOLOGIES.md). Python dependencies are pinned in `apps/api/uv.lock`, web dependencies in `apps/web/package-lock.json`; third-party services run from their upstream images (see `compose.yaml`).

## Design systems in use

The documentation diagrams in `docs/diagrams/` are drawn with the diagram-design system (default skin, which matches the ArchTwin palette; see `.diagram-design`).

## Vendored material

### diagram-design
- Source: https://github.com/cathrynlavery/diagram-design
- Licence: MIT — Copyright (c) 2025 Cathryn Lavery
- Use: design references (style-guide tokens, visual-type references, connector rules, anti-patterns) vendored into `packages/diagram-design-system/` (tokens + rules) and implemented as ArchTwin's export renderer/linter (`apps/api/archtwin/diagrams/`) and canvas styling (`apps/web/src/diagram/`). Full licence text: `packages/diagram-design-system/LICENSE`.

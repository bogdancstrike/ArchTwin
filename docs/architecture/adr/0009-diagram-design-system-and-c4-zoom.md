# ADR-0009: Editorial diagram-design system for all generated diagrams; C4 zoom navigation

- **Status:** Accepted (planning baseline)
- **Date:** 2026-11-08

## Context and problem
Auto-generated diagrams are usually cluttered and inconsistent, which undermines trust in the model.

## Decision
All platform-generated diagrams use the open-source **diagram-design** system (MIT): org-skinnable tokens, visual-type routing, node treatments, ≤2 focal accents, ≤9 primary nodes per view (else overview + detail), and six mandatory connector rules enforced by a **linter** before publish/export. Interactive editing uses React Flow with the same tokens; layout and orthogonal routing by elkjs. C4 views support animated **zoom** from system context (L1) to containers (L2) to components (L3) using React Flow viewport APIs and Motion, honouring reduced motion.

## Alternatives considered
- Mermaid/Structurizr renderers for platform figures — rejected: automatic layouts violate the design rules; kept as interchange formats.
- Custom visual language — rejected: reinventing a documented system.

## Consequences
- Consistent, legible diagrams; enforceable quality.
- Linter and router must be maintained alongside upstream updates (vendored with attribution).

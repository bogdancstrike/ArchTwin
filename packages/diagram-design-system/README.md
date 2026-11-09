# diagram-design-system

Vendored design tokens and rules for every diagram ArchTwin generates (ADR-0009, AT-DIAGRAM_STUDIO-005/006).

Adopted from **diagram-design** by Cathryn Lavery — MIT licence — https://github.com/cathrynlavery/diagram-design
(`references/style-guide.md` default skin and the architecture connector rules). See `THIRD_PARTY_NOTICES.md`.

- `tokens.json` — canonical semantic tokens (paper, ink, muted, soft, rule, accent, link), type scale and rules.
  Copies live in `apps/api/archtwin/diagrams/tokens.json` (export renderer + linter) and `apps/web/src/diagram/tokens.json`
  (interactive canvas); `tests/test_diagram_tokens.py` fails if they drift.
- Organizations can override any token (org skin); exports use the requesting org's tokens only.

Rules enforced by the linter (`apps/api/archtwin/diagrams/render.py`):
1. orthogonal connectors with rounded bends; 2. arrow labels masked with a 6–10 px gap; 3. no overlapping (collinear)
connectors; 4. fanned attach points (no two connectors share an attach point); 5. no connector transits behind a
non-endpoint box; 6. no label mask under a node. Plus: ≤ 9 primary nodes (overview/detail split) and ≤ 2 focal accents.

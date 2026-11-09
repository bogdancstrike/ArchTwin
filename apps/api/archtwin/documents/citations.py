"""Evidence appendix shared by evidence-mode and AI-mode generated documents."""
from __future__ import annotations

from typing import Any


def evidence_section(evidence: list[dict[str, Any]]) -> str:
    return "\n## Evidence\n\n" + "\n".join(
        f"- **{e['id']}** `{e['key']}` — {e['origin']} · {e.get('source_ref') or 'n/a'}"
        f"{(':' + str(e['span'].get('line_start'))) if (e.get('span') or {}).get('line_start') else ''} · rev `{(e.get('source_revision') or '')[:12]}`"
        f" · {e['parser_version']} · confidence {e['confidence']:.2f}" for e in evidence) + "\n"

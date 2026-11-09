"""Exports: Markdown builders (canonical) and the DOCX / PDF / ZIP renderers."""
import io
import json
import uuid
import zipfile
from datetime import UTC, datetime

from docx import Document

from archtwin.architecture.builder import build
from archtwin.exports import builders, render
from archtwin.exports.blocks import parse, runs
from archtwin.exports.service import Collection, Item
from tests.conftest import edge, obs

MD = """# Title

Intro with **bold**, `code` and [a link](https://example.com).

## Section

* one
* two

1. first
2. second

| A | B |
|---|---|
| x | y \\| z |

```mermaid
flowchart LR
  a --> b
```

> a quote → with unicode
"""


def graph():
    g = build([obs("system:s", "software-system", name="Shop"), obs("container:s/api", "container", name="api"),
               obs("container:s/db", "database", name="orders-db"), obs("component:s/api/orders", "component", name="orders"),
               obs("endpoint:s/api/POST /orders", "api-endpoint", name="POST /orders", attrs={"method": "POST", "path": "/orders"}),
               edge("system:s", "contains", "container:s/api"), edge("system:s", "contains", "container:s/db"),
               edge("container:s/api", "contains", "component:s/api/orders"), edge("container:s/api", "exposes", "endpoint:s/api/POST /orders"),
               edge("container:s/api", "writes", "container:s/db", attrs={"protocol": "postgresql"})])
    g["snapshot"] = {"id": uuid.uuid4(), "version": 7, "created_at": datetime.now(UTC), "inputs": {"scans": [{"connector_id": "c1", "revision": "abc123"}]}}
    return g


def test_block_parser_and_inline_runs():
    kinds = [b.kind for b in parse(MD)]
    assert kinds == ["heading", "para", "heading", "bullets", "numbers", "table", "code", "quote"]
    t = next(b for b in parse(MD) if b.kind == "table")
    assert t.rows == [["A", "B"], ["x", "y \\| z"]]
    assert ("bold", "bold") in runs("a **bold** b") and ("code", "code") in runs("`code`")
    assert runs("[a link](https://x.y)") == [("a link (https://x.y)", "")]


def test_architecture_markdown_has_levels_tables_and_mermaid():
    md = builders.architecture_md(graph(), "Shop")
    assert "snapshot v7" in md and "## Level 1 — System context" in md and "## Level 2 — Shop" in md
    assert "### Level 3 — api components" in md and "| POST | /orders | api |" in md
    assert md.count("```mermaid") >= 2 and "orders-db" in md


def test_flow_markdown_has_sequence_and_steps():
    f = {"id": "f1", "name": "POST /orders", "kind": "endpoint", "length": 1, "confidence": 0.9, "distributed": False, "systems": ["Shop"],
         "participants": [{"key": "a", "name": "api"}, {"key": "b", "name": "orders-db"}],
         "steps": [{"from": "a", "to": "b", "kind": "writes", "label": "INSERT", "protocol": "postgresql", "origins": ["static"], "confidence": 0.9}]}
    md = builders.flow_md(f)
    assert "sequenceDiagram" in md and "p0->>p1: INSERT" in md and "| 1 | api | writes | orders-db |" in md


def test_drift_markdown_lists_filters_and_evidence():
    f = {"id": uuid.uuid4(), "title": "api calls cache", "severity": "medium", "verdict": "drift", "status": "new", "rule_id": "DR-EDGE-ADDED-001",
         "rule_version": "1.0", "subject_key": "x|calls|y", "first_seen": datetime.now(UTC), "last_seen": datetime.now(UTC), "occurrences": 2,
         "expected": None, "actual": {"kind": "calls"}, "evidence": [{"origin": "static", "source_ref": "compose.yaml", "span": {"line_start": 4},
                                                                      "source_revision": "abcdef1234", "parser_version": "compose/1"}]}
    md = builders.drift_md([f], "Shop", None, {"status": "open", "verdict": None})
    assert "Filters: status=open" in md and "`compose.yaml:4` @ abcdef1234" in md and '"actual"' in md


def test_docx_pdf_and_zip_renderers():
    col = Collection("decisions", {"id": uuid.uuid4(), "slug": "shop", "title": "Shop"}, "Shop — Decision records", MD,
                     [Item("ADR-0001-a", "ADR-0001 a", "# a"), Item("ADR-0002-b", "ADR-0002 b", "# b")])
    d = render(col, "docx")
    assert d.filename.startswith("shop-decisions-") and d.filename.endswith(".docx")
    doc = Document(io.BytesIO(d.body))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Title" in text and "Mermaid diagram" in text and len(doc.tables) == 1
    p = render(col, "pdf")
    assert p.body.startswith(b"%PDF") and p.media_type == "application/pdf"
    m = render(col, "md")
    assert m.body.decode() == MD
    z = render(col, "zip")
    data = b"".join(z.stream)
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert "manifest.json" in names and "items/ADR-0001-a.md" in names and any(n.endswith(".pdf") for n in names)
    man = json.loads(zipfile.ZipFile(io.BytesIO(data)).read("manifest.json"))
    assert man["project"]["slug"] == "shop" and man["items"][0]["file"] == "ADR-0001-a.md"


def test_zip_manifest_carries_snapshot_and_revisions():
    g = graph()
    col = Collection("architecture", {"id": uuid.uuid4(), "slug": "shop", "title": "Shop"}, "Shop", builders.architecture_md(g, "Shop"),
                     [Item("architecture", "Architecture", "x")], g["snapshot"])
    man = col.manifest()
    assert man["snapshot"]["version"] == 7 and man["source_revisions"][0]["revision"] == "abc123"

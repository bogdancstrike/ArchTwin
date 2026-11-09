"""Every evidence-mode document type renders from a real analyzed repository and cites evidence."""
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from archtwin.architecture import builder
from archtwin.connectors.analyzers.repo import analyze_repository
from archtwin.documents import engine
from archtwin.documents.doctypes import DOC_TYPES

SNAP = {"version": 3, "manifest_hash": "abc123def4567890", "id": "s"}


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    root = tmp_path_factory.mktemp("shop")
    files = {"compose.yaml": "services:\n  api:\n    build: .\n    command: uvicorn app.main:app\n    environment:\n      DB: postgresql://db:5432/x\n"
                             "  db:\n    image: postgres:17\n",
             "Dockerfile": "FROM python:3.12\n", "app/__init__.py": "", "app/svc/__init__.py": "",
             "app/main.py": "from fastapi import FastAPI\nfrom app.svc.store import Repo\napp = FastAPI()\n@app.get('/items')\ndef items(r: Repo):\n    return r.all()\n",
             "app/svc/store.py": "class Item(Base):\n    __tablename__ = 'items'\n    id = Column(Integer, primary_key=True)\n    name = Column(String)\n\n"
                                 "class Repo:\n    def all(self):\n        return []\n",
             "docs/adr/0001-use-postgres.md": "# ADR 1: Use PostgreSQL\n"}
    for k, v in files.items():
        (root / k).parent.mkdir(parents=True, exist_ok=True)
        (root / k).write_text(v)
    r = analyze_repository(Path(root), "rev", "shop")
    obs = [{"id": uuid.uuid4(), "connector_id": "c", "origin": o.origin, "subject_kind": o.subject_kind, "subject_key": o.subject_key, "kind": o.kind,
            "name": o.name, "attributes": o.attributes, "source_ref": o.source_ref, "source_revision": "rev", "evidence": o.evidence,
            "observed_at": datetime.now(UTC), "parser_version": o.parser_version, "confidence": o.confidence, "sensitive": False} for o in r.observations]
    return builder.build(obs)


@pytest.mark.parametrize("key", [k for k, d in DOC_TYPES.items() if d.mode == "evidence"])
def test_evidence_doc_types_render_and_cite(graph, key):
    extra = {"app_adrs": [{"number": "0001", "title": "Adopt X", "status": "accepted", "source": "ArchTwin", "ref": ""}]} if key == "decision-log" else None
    body, evidence, _ = engine.render(key, graph, "Shop", SNAP, extra)
    assert body.startswith("# Shop — ") and "## Evidence" in body
    cited = {e["id"] for e in evidence}
    assert cited and all(f"[{i}]" in body for i in cited)                      # only evidence that is actually cited is listed


def test_specific_content(graph):
    dm, _, _ = engine.render("data-model", graph, "Shop", SNAP)
    assert "`items`" in dm and "| `id` | Integer |" in dm and "PK" in dm
    fl, _, _ = engine.render("flows", graph, "Shop", SNAP)
    assert "```mermaid" in fl and "sequenceDiagram" in fl
    dev, _, _ = engine.render("developer-reference", graph, "Shop", SNAP)
    assert "`GET /items`" in dev and "class **Repo**" in dev
    log, _, _ = engine.render("decision-log", graph, "Shop", SNAP, {"app_adrs": []})
    assert "ADR 1: Use PostgreSQL" in log


def test_ai_types_are_not_rendered_as_templates(graph):
    ai = [k for k, d in DOC_TYPES.items() if d.mode == "ai"]
    assert {"user-guide", "prd", "arf", "developer-guide"} <= set(ai)
    with pytest.raises(Exception, match="422"):
        engine.render("prd", graph, "Shop", SNAP)

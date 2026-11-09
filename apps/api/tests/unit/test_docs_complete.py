"""Generated documentation is complete: deterministic documents cover every endpoint and flow; AI documents are drafted
section by section from a full outline (fake LLM mode — no tokens), with valid citations and a table of contents."""
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from archtwin.architecture import builder, flows
from archtwin.connectors.analyzers.repo import analyze_repository
from archtwin.documents import ai_writer, engine
from archtwin.documents.doctypes import DOC_TYPES
from archtwin.documents.features import FeatureIndex, flowchart
from archtwin.intelligence import usage

SNAP = {"version": 2, "manifest_hash": "abc123def4567890", "id": "s"}
FILES = {
    "compose.yaml": "services:\n  api:\n    build: .\n    ports: ['8080:8000']\n    command: uvicorn app.main:app\n"
                    "    environment:\n      DB: postgresql://db:5432/x\n  db:\n    image: postgres:17\n",
    "Dockerfile": "FROM python:3.12\n", "app/__init__.py": "",
    "app/main.py": "from fastapi import FastAPI\nfrom app import orders, invoices\napp = FastAPI()\napp.include_router(orders.router)\n"
                   "app.include_router(invoices.router)\n",
    "app/store.py": "import sqlite3\n\nclass Order(Base):\n    __tablename__ = 'orders'\n    id = Column(Integer, primary_key=True)\n"
                    "    total = Column(Integer)\n\ndef save(x):\n    sqlite3.connect('x.db')\n",
    "app/orders.py": "from fastapi import APIRouter\nfrom app import store\nrouter = APIRouter(prefix='/api/orders')\n\n"
                     "@router.get('')\ndef list_orders():\n    return []\n\n@router.post('')\ndef create_order():\n    store.save(1)\n\n"
                     "@router.get('/{order_id}')\ndef get_order(order_id: str):\n    return {}\n",
    "app/invoices.py": "from fastapi import APIRouter\nfrom app import store\nrouter = APIRouter(prefix='/api/invoices')\n\n"
                       "@router.get('/{invoice_id}')\ndef get_invoice(invoice_id: str):\n    store.save(1)\n",
    "docs/adr/0001-use-postgres.md": "# ADR 1: Use PostgreSQL\n",
}


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    root = tmp_path_factory.mktemp("shop")
    for k, v in FILES.items():
        (root / k).parent.mkdir(parents=True, exist_ok=True)
        (root / k).write_text(v)
    r = analyze_repository(Path(root), "rev", "shop")
    obs = [{"id": uuid.uuid4(), "connector_id": "c", "origin": o.origin, "subject_kind": o.subject_kind, "subject_key": o.subject_key, "kind": o.kind,
            "name": o.name, "attributes": o.attributes, "source_ref": o.source_ref, "source_revision": "rev", "evidence": o.evidence,
            "observed_at": datetime.now(UTC), "parser_version": o.parser_version, "confidence": o.confidence, "sensitive": False} for o in r.observations]
    return builder.build(obs)


def test_feature_index_skips_namespaces_and_verbs_and_merges_plurals():
    paths = [f"ACTION qdata_{v}_{n}" for v in ("create", "get", "delete") for n in ("investigation", "upload", "alert", "parser", "profile",
                                                                                     "source", "entity", "graph", "doc")] + \
            ["ACTION investigations_append", "ACTION investigations_create", "POST /api/v1/category-sets", "GET /api/v1/category-sets/{id}"]
    fx = FeatureIndex(paths)
    assert "qdata" in fx.namespaces and "api" not in fx.namespaces          # 'api' is generic and dropped before counting
    assert fx.of("ACTION qdata_create_investigation") == fx.of("ACTION investigations_append") == "Investigations"
    assert fx.of("GET /api/v1/category-sets/{id}") == "Category sets"
    assert "-->|calls| b" in flowchart([("a", 'A "x"', "box"), ("b", "B", "db")], [("a", "b", "calls")])


def test_deterministic_docs_cover_every_endpoint_and_flow(graph):
    eps = [n["attributes"] for n in graph["nodes"].values() if n["kind"] == "api-endpoint"]
    assert len(eps) >= 4
    fl = flows.recognize(graph)["flows"]
    iface, _, _ = engine.render("interface-catalog", graph, "Shop", SNAP)
    testing, _, _ = engine.render("testing", graph, "Shop", SNAP)
    flows_doc, _, _ = engine.render("flows", graph, "Shop", SNAP)
    for a in eps:
        assert f"`{a['path']}`" in iface, a
        assert f"`{a['method']} {a['path']}`" in testing, a
        assert f"$BASE_URL{a['path']}" in testing
    for f in fl:
        assert f["name"].replace("{", "\\{").replace("}", "\\}").replace("_", "\\_") in flows_doc
    assert testing.count("### Scenario ") == len(fl) and "404 for an unknown order_id" in testing
    assert "**Description.**" in flows_doc and "**Components involved:**" in flows_doc and "## Flow index" in flows_doc


def test_overview_has_diagrams_counts_and_features(graph):
    ov, _, _ = engine.render("system-overview", graph, "Shop", SNAP, {"app_adrs": [{"number": "0001", "title": "Adopt X", "status": "accepted",
                                                                                     "source": "ArchTwin", "ref": ""}]})
    assert ov.count("```mermaid") >= 2 and "flowchart LR" in ov and "&#34;" not in ov
    assert "## Functional areas" in ov and "Orders" in ov and "Invoices" in ov and "Adopt X" in ov
    assert re.search(r"\| HTTP endpoints / actions \| \d+ \|", ov)
    dm, _, _ = engine.render("data-model", graph, "Shop", SNAP)
    assert "erDiagram" in dm and "`orders`" in dm


@pytest.mark.parametrize("key", [k for k, d in DOC_TYPES.items() if d.mode == "ai"])
async def test_ai_docs_are_drafted_section_by_section(graph, key, monkeypatch):
    async def noop(*a, **k):
        return None

    async def no_passages(ctx, sections, dt, start):
        return {}, []

    monkeypatch.setattr(ai_writer.flags, "require", noop)
    monkeypatch.setattr(ai_writer, "_passages", no_passages)
    monkeypatch.setattr(usage, "check", noop)
    monkeypatch.setattr(usage, "record", noop)
    ctx = SimpleNamespace(org_id=uuid.uuid4(), project_id=uuid.uuid4(), actor_id=uuid.uuid4())
    dt = DOC_TYPES[key]
    context = engine._context(graph, "Shop", SNAP)
    context[0]["app_adrs"] = [{"number": "0001", "title": "Adopt X", "status": "accepted", "outcome": "We adopt X."}]
    body, used, cov = await ai_writer.write(ctx, dt, graph, "Shop", SNAP, context)
    planned = ai_writer.plan(dt, context[0])
    assert len(planned) >= len([s for s in dt.sections if not s.per_feature]) + any(s.per_feature for s in dt.sections) >= 10
    for ps in planned:                                              # every section of the outline is present, in order, in the TOC
        assert f"## {ps.n}. {ps.title}" in body and f"{ps.n}. [{ps.title}]" in body
    assert body.startswith(f"# Shop — {dt.title}") and "AI draft — review required" in body and "## Contents" in body
    cited = set(re.findall(r"\[(E\d+)\]", body.split("\n## Evidence")[0]))
    assert cited and cited == {e["id"] for e in used}               # citations valid: every cited id is listed, nothing else
    assert cov["sections"] == [p.title for p in planned] and cov["ai_draft"]
    if any(s.per_feature for s in dt.sections):
        assert any(p.feature in ("Orders", "Invoices") for p in planned)


def test_section_facts_are_feature_filtered_and_bounded(graph):
    ctx_data, _, _ = engine._context(graph, "Shop", SNAP)
    fs = ai_writer.facts(ctx_data)
    ps = next(p for p in ai_writer.plan(DOC_TYPES["prd"], ctx_data) if p.feature == "Orders")
    picked = ai_writer.section_facts(fs, ps, set())
    assert picked and all(f.feature in ("", "Orders") for f in picked)
    assert any("invoices" in f.text for f in fs) and not any("/api/invoices" in f.text for f in picked)
    big = ai_writer.section_facts(fs * 400, ps, set(), budget=500)
    assert sum(len(f.text) for f in big) < 500 * 6

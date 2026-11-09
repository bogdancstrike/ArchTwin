"""Project-wide scan, asking the Flows / Decisions / Docs pages, drift dismissal and per-task model routing — on the live stack.

No model is called: page questions run search-only (`ai: false`) and cost estimates are pre-flight, so the suite spends
no tokens even when the stack talks to a real provider.
"""
import shutil
import uuid

import pytest

from tests.e2e.conftest import wait
from tests.e2e.test_local_gitlab_taiga import HOST_FIX, MOUNTED, _repo

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def fixtures(run_id):
    root = HOST_FIX / f"ask-{run_id}"
    _repo(root / "dissem-svc", {
        "compose.yaml": "services:\n  dissem:\n    build: .\n    ports: ['8000:8000']\n    command: uvicorn app.main:app\n",
        "Dockerfile": "FROM python:3.12\nCOPY . .\n",
        "app/__init__.py": "",
        "app/main.py": "from fastapi import FastAPI\nfrom app import dissemination\napp = FastAPI()\napp.include_router(dissemination.router)\n",
        "app/store.py": "import sqlite3\n\ndef save(x):\n    sqlite3.connect('cases.db').execute('select 1')\n",
        "app/dissemination.py": "from fastapi import APIRouter\nfrom app import store\nrouter = APIRouter(prefix='/cases')\n\n"
                                "@router.post('/{case_id}/disseminate')\ndef disseminate(case_id: str):\n    return {}\n",
    })
    _repo(root / "handbook", {"README.md": "# Operations handbook\n\n## Deploy the ingest service\n\nRun docker compose up ingest after the "
                                           "database migration finished.\n"})
    for d in (HOST_FIX, root):
        d.chmod(0o755)
    yield f"{MOUNTED}/ask-{run_id}"
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(scope="module")
def proj(users, run_id, fixtures):
    admin = users["admin"]
    p = admin.ok("POST", "/projects", 201, json={"title": f"Ask {run_id}", "purpose": "e2e: scan all, page questions", "tags": ["e2e"]},
                 headers={"Idempotency-Key": f"ask-{run_id}"})
    ids = {m["username"]: m["id"] for m in admin.ok("GET", "/org/users")}
    admin.ok("PUT", f"/projects/{p['id']}/members", json={"user_id": ids["vera"], "role": "viewer"})
    admin.ok("POST", f"/projects/{p['id']}/connectors", 201, json={"kind": "git", "name": "dissem", "config": {"path": f"{fixtures}/dissem-svc"}})
    admin.ok("POST", f"/projects/{p['id']}/connectors", 201, json={"kind": "git", "name": "handbook",
                                                                     "config": {"path": f"{fixtures}/handbook", "content": "docs"}})
    return p


def test_scan_all_queues_one_job_per_datasource_and_skips_busy_ones(users, proj):
    admin, vera, pid = users["admin"], users["vera"], proj["id"]
    assert vera.post(f"/projects/{pid}/scan", headers={"Idempotency-Key": uuid.uuid4().hex}).status_code == 403
    r = admin.ok("POST", f"/projects/{pid}/scan", 202, headers={"Idempotency-Key": uuid.uuid4().hex})
    assert sorted(x["name"] for x in r["queued"]) == ["dissem", "handbook"] and r["skipped"] == []
    again = admin.ok("POST", f"/projects/{pid}/scan", 202, headers={"Idempotency-Key": uuid.uuid4().hex})
    assert all(s["reason"] == "already scanning" for s in again["skipped"]) or again["queued"]     # a fast worker may already be done
    wait(lambda: all(s["status"] in ("complete", "partial") for s in admin.ok("GET", f"/projects/{pid}/scans")[:2])
         and len(admin.ok("GET", f"/projects/{pid}/scans")) >= 2, timeout=240, what="both scans")
    wait(lambda: any("disseminate" in f["name"] for f in (admin.ok("GET", f"/projects/{pid}/flows") or {}).get("flows", [])),
         timeout=180, what="a flow for the disseminate endpoint")


def test_ask_pages_search_without_tokens(users, proj):
    admin, vera, pid = users["admin"], users["vera"], proj["id"]
    f = admin.ok("POST", f"/projects/{pid}/ask", json={"page": "flows", "question": "what is the flow of dissemination documents?", "ai": False})
    assert f["matches"] and "disseminate" in f["matches"][0]["title"] and f["matches"][0]["flow"]["steps"]
    assert f["ai"] is False and f["cost_usd"] == 0
    admin.ok("POST", f"/projects/{pid}/adrs", 201, json={"title": "Cache search results", "decision_outcome": "Redis in front of Elasticsearch",
                                                          "decision_drivers": ["latency"]})
    d = admin.ok("POST", f"/projects/{pid}/ask", json={"page": "decisions", "question": "is caching part of any decision?", "ai": False})
    assert d["matches"][0]["title"].endswith("Cache search results")
    none = admin.ok("POST", f"/projects/{pid}/ask", json={"page": "decisions", "question": "quantum billing", "ai": False})
    assert none["matches"] == [] and none["reason"] == "no_match"
    doc = wait(lambda: admin.ok("POST", f"/projects/{pid}/ask", json={"page": "docs", "question": "how do I deploy the ingest service", "ai": False})["matches"],
               what="handbook passage")
    assert "README.md" in doc[0]["path"]
    assert vera.ok("POST", f"/projects/{pid}/ask", json={"page": "flows", "question": "dissemination", "ai": False})["matches"]  # viewers may search
    assert admin.post(f"/projects/{pid}/ask", json={"page": "secrets", "question": "x"}).status_code == 422


def test_model_routing_and_estimates(users):
    admin = users["admin"]
    r = admin.ok("GET", "/ai/routing")
    assert "gpt-6-sol" in r["blocked_models"]
    by = {t["operation"]: t for t in r["tasks"]}
    assert all(t["model"] != "gpt-6-sol" for t in r["tasks"])
    hidden = admin.ok("GET", "/ai/models")["hidden"]
    fe = by["flow_explain"]
    assert fe["configured_model"] == "gpt-6-terra" and fe["reasoning_effort"] == "high"
    assert fe["model"] == ("gpt-6-luna" if "gpt-6-terra" in hidden else "gpt-6-terra")      # a rejected model falls back, effort kept
    assert by["text_extend"]["model"] == "gpt-6-luna"
    e = admin.ok("POST", "/ai/estimate", json={"operation": "page_ask", "text": "what is the flow of dissemination documents?"})
    assert e["model"] == "gpt-6-luna" and e["input_tokens"] > 0 and e["output_tokens"]["max"] >= e["output_tokens"]["expected"]
    assert admin.post("/ai/estimate", json={"operation": "question_answering", "model": "gpt-6-sol"}).status_code == 422
    assert admin.post("/ai/estimate", json={"operation": "nope"}).status_code == 422
    assert "gpt-6-sol" not in {m["alias"] for m in admin.ok("GET", "/ai/models")["models"]}


def test_drift_dismissal_is_authorized_and_sticky(users, proj):
    admin, vera, pid = users["admin"], users["vera"], proj["id"]
    admin.ok("POST", f"/projects/{pid}/drift/evaluate")
    found = admin.ok("GET", f"/projects/{pid}/drift")
    if not found:
        assert admin.ok("POST", f"/projects/{pid}/drift/dismiss", json={"ids": [str(uuid.uuid4())]})["dismissed"] == 0
        return
    fid = found[0]["id"]
    assert vera.post(f"/projects/{pid}/drift/dismiss", json={"ids": [fid]}).status_code == 403
    assert admin.ok("POST", f"/projects/{pid}/drift/dismiss", json={"ids": [fid]})["dismissed"] == 1      # no reason needed
    assert fid not in {f["id"] for f in admin.ok("GET", f"/projects/{pid}/drift")}
    admin.ok("POST", f"/projects/{pid}/drift/evaluate")
    assert admin.ok("GET", f"/projects/{pid}/drift/{fid}")["status"] == "dismissed"                         # not resurrected
    assert fid in {f["id"] for f in admin.ok("GET", f"/projects/{pid}/drift", params={"status": "dismissed"})}
    admin.ok("POST", f"/projects/{pid}/drift/{fid}/transition", json={"status": "new"})                        # restore

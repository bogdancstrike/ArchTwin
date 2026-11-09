"""Distributed systems across repositories: a gateway (routing table, declared endpoints, no Compose) in front of a
backend with CLI roles sharing one image, router factories with f-string prefixes and a plugin registry."""
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from archtwin.architecture import builder, flows
from archtwin.connectors.analyzers.repo import analyze_repository

BACKEND = {
    "docker-compose.yml": "services:\n  bootstrap:\n    image: backend:dev\n    build: .\n    command: [bootstrap]\n"
                          "  query:\n    image: backend:dev\n    command: [query]\n    ports: ['8080:8080']\n"
                          "  ingest:\n    image: backend:dev\n    command: [ingest]\n",
    "Dockerfile": 'FROM python:3.12\nCOPY src ./src\nENTRYPOINT ["tini", "--", "backend"]\nCMD ["query"]\n',
    "pyproject.toml": '[project]\nname = "backend"\n[project.scripts]\nbackend = "backend.cli:app"\n',
    "src/backend/__init__.py": "",
    "src/backend/cli.py": 'import uvicorn\nQUERY_APP = "backend.entry.query:create_app"\n\ndef query():\n    uvicorn.run(QUERY_APP, factory=True)\n\n'
                          "def ingest():\n    from backend.entry.ingest import run\n    run()\n\ndef bootstrap():\n    from backend.entry import seed\n",
    "src/backend/entry/__init__.py": "",
    "src/backend/entry/query.py": 'from fastapi import FastAPI\nPLUGINS = {"cases": "backend.cases.module:CasesModule"}\n\ndef create_app():\n    return FastAPI()\n',
    "src/backend/entry/ingest.py": "def run():\n    pass\n",
    "src/backend/entry/seed.py": "",
    "src/backend/cases/__init__.py": "",
    "src/backend/cases/module.py": "from backend.cases import routes\n\nclass CasesModule:\n    pass\n",
    "src/backend/cases/routing.py": 'from fastapi import APIRouter\nAPI_PREFIX = "/api/cases"\n\ndef cases_router(path: str = "") -> APIRouter:\n'
                                     '    return APIRouter(prefix=f"{API_PREFIX}{path}")\n',
    "src/backend/cases/routes.py": "from backend.cases.routing import cases_router\nfrom backend.store import db\n\nrouter = cases_router(\"/{case_id}\")\n\n"
                                   "@router.get('/files')\ndef files(case_id: str):\n    return []\n",
    "src/backend/store/__init__.py": "", "src/backend/store/db.py": "import sqlite3\n",
}
GATEWAY = {
    "Dockerfile": 'FROM python:3.12\nCOPY . .\nEXPOSE 4000\nCMD ["gunicorn", "app:app"]\n',
    "app.py": "from flask import Flask\napp = Flask(__name__)\n",
    "service/api_handler.py": "import json\nimport requests\nprocessor_map = json.load(open('maps/processor_map.json'))\n\ndef action_handler():\n    pass\n",
    "maps/endpoint.json": '{"namespaces": [{"name": "api", "description": ""}], "models": {}, "endpoints": [{"namespace": "api", "operation_name": "action",'
                          ' "request_method": ["post"], "exec_method": {"module_name": "service.api_handler", "method_name": "action_handler"}}]}',
    "maps/processor_map.json": '{"list_files": {"service": "acme-backend-query:8080", "endpoint": "/api/cases/{case_id}/files", "method": "get"},'
                               ' "missing": {"service": "acme-backend-query:8080", "endpoint": "/api/nothing/here", "method": "post"},'
                               ' "local": {"service": "localhost:5000", "endpoint": "/x", "method": "post"}}',
}


def _write(root: Path, files: dict[str, str]) -> Path:
    for k, v in files.items():
        (root / k).parent.mkdir(parents=True, exist_ok=True)
        (root / k).write_text(v)
    return root


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    obs = []
    for name, files in (("acme-backend", BACKEND), ("acme-gateway", GATEWAY)):
        r = analyze_repository(_write(tmp_path_factory.mktemp(name), files), "rev", name)
        obs += [{"id": uuid.uuid4(), "connector_id": name, "origin": o.origin, "subject_kind": o.subject_kind, "subject_key": o.subject_key,
                 "kind": o.kind, "name": o.name, "attributes": o.attributes, "source_ref": o.source_ref, "source_revision": "rev",
                 "evidence": o.evidence, "observed_at": datetime.now(UTC), "parser_version": o.parser_version, "confidence": o.confidence,
                 "sensitive": False} for o in r.observations]
    return builder.build(obs)


def test_roles_of_a_shared_image_run_their_own_code(graph):
    eps = {k for k, n in graph["nodes"].items() if n["kind"] == "api-endpoint" and k.startswith("endpoint:acme-backend/")}
    assert eps == {"endpoint:acme-backend/query/GET /api/cases/{case_id}/files"}      # only the role that serves HTTP; factory prefix resolved
    comps = {k for k, n in graph["nodes"].items() if n["kind"] == "component"}
    assert "component:acme-backend/query/backend.cases" in comps                      # reached through the plugin registry string
    assert not any(k.startswith("component:acme-backend/ingest/backend.cases") for k in comps)


def test_dockerfile_only_repo_with_declared_endpoints_and_routing_table(graph):
    n = graph["nodes"]
    assert "container:acme-gateway/acme-gateway" in n and "endpoint:acme-gateway/acme-gateway/POST /api/action" in n
    act = n["endpoint:acme-gateway/acme-gateway/ACTION list_files"]["attributes"]
    assert act["dispatcher"] == "/api/action" and act["routes_to"] == "acme-backend-query:8080 GET /api/cases/{case_id}/files"


def test_gateway_routes_resolve_to_backend_endpoints_or_service(graph):
    e = graph["edges"]
    assert "endpoint:acme-gateway/acme-gateway/ACTION list_files|calls|endpoint:acme-backend/query/GET /api/cases/{case_id}/files" in e
    assert "endpoint:acme-gateway/acme-gateway/ACTION missing|calls|container:acme-backend/query" in e      # unknown path: the service
    assert not any("ACTION local|calls" in k for k in e)                                                    # localhost is not a service


def test_distributed_endpoint_flow(graph):
    f = {x["name"]: x for x in flows.recognize(graph)["flows"]}
    flow = f["ACTION list_files"]
    assert flow["distributed"] and set(flow["systems"]) == {"acme-gateway", "acme-backend"}
    assert "SQLite (embedded)" in [p["name"] for p in flow["participants"]]

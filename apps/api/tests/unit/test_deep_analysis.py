"""Deeper discovery on an app shaped like a real one (benchmark: image-organizer): compose `extends`, packages under a
subfolder copied by the Dockerfile, resources per component, data volumes, a SPA inside the build context and the
endpoint-level flows that tie them together."""
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from archtwin.architecture import builder, flows
from archtwin.connectors.analyzers.repo import analyze_repository
from archtwin.connectors.analyzers.webui import match_endpoints, normalize

FILES = {
    "docker-compose.yml": "name: organizer\nservices:\n  app:\n    extends:\n      file: docker/compose.${DEVICE:-cpu}.yml\n      service: runtime\n"
                          "    build: .\n    ports: ['8875:8000']\n    volumes:\n      - ${LIBRARY_PATH:-${HOME}}:/library\n      - ./data:/data\n"
                          "      - ./conf/app.yaml:/etc/app.yaml:ro\n",
    "docker/compose.cpu.yml": "services:\n  runtime:\n    build:\n      target: cpu\n",
    "Dockerfile": "FROM node:22 AS ui\nCOPY frontend/ ./\nRUN npm run build\nFROM python:3.12 AS runtime\nWORKDIR /app\nCOPY backend/ ./\n"
                  'CMD ["uvicorn", "--factory", "app.main:create_app"]\n',
    "backend/app/__init__.py": "", "backend/app/api/__init__.py": "", "backend/app/store/__init__.py": "", "backend/app/ai/__init__.py": "",
    "backend/app/main.py": "from fastapi import FastAPI\nfrom app.api import routes\n\ndef create_app():\n    app = FastAPI()\n    app.include_router(routes.create_router())\n    return app\n",
    "backend/app/api/routes.py": "from fastapi import APIRouter\nfrom app.store.db import Store\nfrom app.ai.llm import Client\n\n"
                                 "def create_router():\n    router = APIRouter()\n\n    @router.get('/api/items/{item_id}')\n    def item(item_id: int):\n        return Store().get(item_id)\n\n"
                                 "    @router.post('/api/suggest')\n    def suggest():\n        return Client().ask()\n    return router\n",
    "backend/app/store/db.py": "import sqlite3\n\nclass Store:\n    def get(self, i):\n        return sqlite3.connect('x.db')\n",
    "backend/app/ai/llm.py": "from openai import OpenAI\nimport subprocess\n\nclass Client:\n    def ask(self):\n        subprocess.run(['ffmpeg', '-i', 'x'])\n        return OpenAI()\n",
    "frontend/package.json": '{"name": "ui", "dependencies": {"react": "^19"}}',
    "frontend/src/api.ts": "export const get = (id: number) => fetch(`/api/items/${id}`);\nexport const s = () => fetch('/api/suggest', {method: 'POST'});\n",
}


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    root = tmp_path_factory.mktemp("organizer")
    for k, v in FILES.items():
        (root / k).parent.mkdir(parents=True, exist_ok=True)
        (root / k).write_text(v)
    return analyze_repository(Path(root), "rev", "organizer")


@pytest.fixture(scope="module")
def graph(result):
    return builder.build([{"id": uuid.uuid4(), "connector_id": "c", "origin": o.origin, "subject_kind": o.subject_kind, "subject_key": o.subject_key,
                           "kind": o.kind, "name": o.name, "attributes": o.attributes, "source_ref": o.source_ref, "source_revision": "rev",
                           "evidence": o.evidence, "observed_at": datetime.now(UTC), "parser_version": o.parser_version, "confidence": o.confidence,
                           "sensitive": False} for o in result.observations])


def test_extends_fragment_is_merged_not_a_system(graph):
    systems = {k for k, n in graph["nodes"].items() if n["kind"] == "software-system"}
    assert systems == {"system:organizer"}                                   # docker/compose.cpu.yml is not a second system


def test_packages_under_a_copied_subfolder_are_analyzed(graph):
    comps = {k for k, n in graph["nodes"].items() if n["kind"] == "component"}
    assert {"component:organizer/app/app.api", "component:organizer/app/app.store", "component:organizer/app/app.ai"} <= comps
    eps = {n["name"] for n in graph["nodes"].values() if n["kind"] == "api-endpoint"}
    assert eps == {"GET /api/items/{item_id}", "POST /api/suggest"}           # routes declared inside a router factory


def test_resources_per_component_with_container_rollup(graph):
    e = graph["edges"]
    assert "component:organizer/app/app.store|writes|database:organizer/sqlite" in e
    assert "component:organizer/app/app.ai|calls|external:openai" in e
    assert "component:organizer/app/app.ai|calls|external:organizer/ffmpeg" in e
    assert "container:organizer/app|calls|external:openai" in e and "container:organizer/app|writes|database:organizer/sqlite" in e


def test_data_volumes_but_not_mounted_files(graph):
    vols = {k: n for k, n in graph["nodes"].items() if n["attributes"].get("volume")}
    assert set(vols) == {"container:organizer/volume-library", "container:organizer/volume-data"}     # app.yaml file mount skipped
    assert "container:organizer/app|writes|container:organizer/volume-library" in graph["edges"]


def test_spa_in_build_context_calls_endpoints(graph):
    e = graph["edges"]
    assert "person:user|calls|component:organizer/app/web-ui" in e
    assert "component:organizer/app/web-ui|calls|endpoint:organizer/app/GET /api/items/{item_id}" in e
    assert "component:organizer/app/web-ui|calls|endpoint:organizer/app/POST /api/suggest" in e


def test_endpoint_flows_go_from_user_to_resources(graph):
    f = flows.recognize(graph)
    by = {x["name"]: x for x in f["flows"] if x["kind"] == "endpoint"}
    names = [p["name"] for p in by["POST /api/suggest"]["participants"]]
    assert names[:3] == ["User", "Web UI (React)", "api"] and "OpenAI API" in names and "ffmpeg (external tool)" in names
    assert "SQLite (embedded)" in [p["name"] for p in by["GET /api/items/{item_id}"]["participants"]]


def test_ui_path_matching():
    assert normalize("/api/jobs/${id}/cancel?x=1") == "/api/jobs/{}/cancel"
    eps = {"/api/jobs/{}": ["GET", "DELETE"], "/api/jobs": ["POST"]}
    assert match_endpoints("/api/jobs/{}", eps) == ["GET", "DELETE"] and match_endpoints("/api/nope", eps) == []

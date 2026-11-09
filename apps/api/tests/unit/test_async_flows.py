"""Durable workflows, LISTEN/NOTIFY channels and MCP tools: generic framework patterns (synthetic code, no real app)."""
import uuid
from datetime import UTC, datetime
from pathlib import Path

from archtwin.architecture import builder, flows
from archtwin.connectors.analyzers import async_flows, python_code
from archtwin.connectors.analyzers.repo import analyze_repository

COMPOSE = """
x-env: &env
  APP_DATABASE_URL: postgresql://app:pw@db:5432/app
  APP_TEMPORAL_ADDRESS: temporal:7233
services:
  db: {image: "postgres:17", networks: [app]}
  temporal: {image: "temporalio/auto-setup:1.25", networks: [app]}
  gateway: {image: "ghcr.io/berriai/litellm:main", networks: [app]}
  search: {image: "searxng/searxng", networks: [data]}
  api:
    build: ./svc
    command: ["uvicorn", "app.api:app"]
    environment: {<<: *env}
    networks: [app]
  worker:
    build: ./svc
    command: ["python", "-m", "app.worker"]
    environment: {<<: *env, APP_LLM_BASE_URL: "http://gateway:4000/v1", OPENAI_API_KEY: x, APP_MCP_URL: "http://gateway:4000/mcp/app"}
    networks: [app]
  tools:
    build: ./svc
    command: ["python", "-m", "app.tools"]
    environment: {APP_DATABASE_URL: "postgresql://app:pw@db:5432/app"}
    networks: [app, data]
  migrate:
    build: ./svc
    command: ["alembic", "upgrade", "head"]
    environment: {<<: *env}
    networks: [app]
"""

FILES = {
    "svc/app/__init__.py": "",
    "svc/app/config.py": "class Settings:\n    temporal_address: str = 'localhost:7233'\n    llm_base_url: str = ''\n",
    "svc/app/db.py": (
        "from sqlalchemy import text\n\n"
        "async def notify(conn, channel: str, payload: str = '') -> None:\n"
        "    await conn.execute(text('SELECT pg_notify(:c, :p)'), {'c': channel, 'p': payload})\n\n"
        "class Hub:\n"
        "    async def subscribe(self, channel: str):\n"
        "        await self.conn.add_listener(channel, self.cb)\n\n"
        "def order_channel(oid) -> str:\n"
        "    return f'order_{oid}'\n"),
    "svc/app/api.py": (
        "from fastapi import FastAPI\nfrom app.config import Settings\nfrom app.db import notify, Hub\nfrom app import temporal\n"
        "app = FastAPI()\nhub = Hub()\n\n"
        "@app.post('/orders')\nasync def create_order(conn):\n"
        "    c = await temporal.client(Settings().temporal_address)\n"
        "    await c.start_workflow('OrderWorkflow', 1, id='o', task_queue='main')\n\n"
        "@app.get('/orders/estimate')\nasync def estimate():\n    return 1\n\n"
        "@app.get('/orders/{oid}/events')\nasync def events(oid):\n"
        "    async with hub.subscribe(f'order_{oid}') as s:\n        yield s\n"),
    "svc/app/temporal.py": "from temporalio.client import Client\n\nasync def client(addr):\n    return await Client.connect(addr)\n",
    "svc/app/llm.py": "from openai import AsyncOpenAI\n\nasync def complete(prompt):\n    return await AsyncOpenAI().chat.completions.create(model='m', messages=[])\n",
    "svc/app/mcpcall.py": ("from mcp.client.streamable_http import streamablehttp_client\n\n"
                           "async def call(tool):\n    async with streamablehttp_client('x') as s:\n        return await s.call_tool(tool, {})\n"),
    "svc/app/acts.py": (
        "from temporalio import activity\nfrom app import llm, mcpcall\nfrom app.db import notify, order_channel\n\n"
        "@activity.defn\nasync def think(x):\n    return await llm.complete(x)\n\n"
        "@activity.defn\nasync def use_tool(x):\n    return await mcpcall.call(x)\n\n"
        "@activity.defn\nasync def persist(conn, oid):\n    await notify(conn, order_channel(oid), 'e')\n"),
    "svc/app/flows.py": (
        "from temporalio import workflow\nfrom app import acts\n\n"
        "@workflow.defn\n# the order saga\nclass OrderWorkflow:\n    @workflow.run\n    async def run(self, oid):\n"
        "        await workflow.execute_activity(acts.think, oid)\n        await workflow.execute_activity(acts.use_tool, oid)\n"
        "        await workflow.execute_activity(acts.persist, oid)\n"),
    "svc/app/worker.py": (
        "from temporalio.worker import Worker\nfrom app.flows import OrderWorkflow\nfrom app import acts, temporal\nfrom app.config import Settings\n\n"
        "async def main():\n    c = await temporal.client(Settings().temporal_address)\n"
        "    await Worker(c, task_queue='main', workflows=[OrderWorkflow], activities=[acts.think]).run()\n"),
    "svc/app/tools.py": (
        "from mcp.server.fastmcp import FastMCP\nimport pymongo\nserver = FastMCP('tools')\nSEARCH = 'http://search:8080'\n\n"
        "@server.tool()\nasync def find_docs(q: str):\n    return q\n"),
    "svc/alembic/env.py": "from app import config\n",
}


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "compose.yaml").write_text(COMPOSE)
    for rel, body in FILES.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body)
    return tmp_path


def _edges(r) -> set[tuple[str, str, str]]:
    return {(o.attributes["source"], o.kind, o.attributes["target"]) for o in r.observations if o.subject_kind == "edge"}


def test_detector_patterns(tmp_path: Path):
    root = _repo(tmp_path) / "svc"
    files = list(root.rglob("*.py"))
    mods = python_code.analyze(root, files, [], python_code.package_roots(root, files, [], []))
    res = async_flows.analyze(mods)
    assert res["app.flows"].workflows == {"OrderWorkflow": 6}                      # the class line, despite the comment
    assert {n for n, _ in res["app.flows"].activity_calls} == {"think", "use_tool", "persist"}
    assert res["app.worker"].worker_queues == ["main"]
    assert [c for c, _ in res["app.acts"].notifies] == ["order_*"]                  # through the channel-factory function
    assert [c for c, _ in res["app.api"].listens] == ["order_*"]
    assert [t for t, _ in res["app.tools"].mcp_tools] == ["find_docs"]
    assert res["app.mcpcall"].mcp_client
    assert async_flows.channel_pattern("mission_{m.hex}_{n}", True) == "mission_*_*"
    assert async_flows.channel_pattern("conv_", False) == "conv_*"                   # literal prefix completed at run time
    assert async_flows.channel_pattern("{x}", True) is None                         # nothing literal: unknowable


def test_repository_elements_and_precision(tmp_path: Path):
    r = analyze_repository(_repo(tmp_path), "rev", "shop")
    e = _edges(r)
    api, worker, tools, migrate = (f"container:shop/{n}" for n in ("api", "worker", "tools", "migrate"))
    wf, ch = "workflow:shop/OrderWorkflow", "channel:shop/order_*"
    assert (api, "publishes", wf) in e and (worker, "consumes", wf) in e
    assert ("container:shop/temporal", "contains", wf) in e and ("container:shop/db", "contains", ch) in e
    assert (api, "consumes", ch) in e
    # the SDK talks to the configured gateway, never to the SaaS directly; the API holds no LLM configuration
    assert (worker, "calls", "container:shop/gateway") in e
    assert not any(t == "external:openai" for _, _, t in e)
    # a migration job handed the workflow-engine address by a shared YAML block does not use it
    assert (migrate, "calls", "container:shop/temporal") not in e and (api, "calls", "container:shop/temporal") in e
    # only the service on the data network reaches the store configured at run time and the isolated search service
    assert (tools, "writes", "external:mongodb") in e and (api, "writes", "external:mongodb") not in e
    assert (tools, "calls", "container:shop/search") in e and (api, "calls", "container:shop/search") not in e
    tool_eps = [o.name for o in r.observations if o.subject_kind == "node" and o.kind == "api-endpoint" and o.attributes.get("protocol") == "mcp"]
    assert tool_eps == ["MCP find_docs"]
    wf_node = next(o for o in r.observations if o.subject_kind == "node" and o.subject_key == wf and o.attributes.get("effects"))
    assert {fx["label"].split(" via ")[0] for fx in wf_node.attributes["effects"]} >= {"OpenAI", "MCP tools", "NOTIFY order_*"}


def test_flows_follow_workflows_and_channels(tmp_path: Path):
    r = analyze_repository(_repo(tmp_path), "rev", "shop")
    obs = [{"id": uuid.uuid4(), "connector_id": uuid.UUID(int=1), "scan_id": uuid.UUID(int=2), "observed_at": datetime.now(UTC),
            **o.model_dump()} for o in r.observations]
    by = {x["name"]: x for x in flows.recognize(builder.build(obs, {}))["flows"]}

    def hops(name):
        names = {p["key"]: p["name"] for p in by[name]["participants"]}
        return [(names[s["from"]], s["kind"], names[s["to"]]) for s in by[name]["steps"]]
    order = hops("POST /orders")
    assert ("api", "starts", "OrderWorkflow") in order and ("OrderWorkflow", "executes", "worker") in order
    assert ("worker", "calls", "gateway") in order and ("worker", "publishes", "order_*") in order
    assert ("order_*", "delivers", "api") in order
    assert not any(h[1] == "starts" for h in hops("GET /orders/estimate")) if "GET /orders/estimate" in by else True
    assert "Workflow: OrderWorkflow" in by and "Notification: order_*" in by
    assert ("api", "streams", "GET /orders/{oid}/events") in hops("Notification: order_*")

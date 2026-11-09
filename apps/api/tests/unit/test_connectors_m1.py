"""Phase-02 M1 connectors: webhook verification, Kafka code detection, OTel service graph, GitHub (HTTP mocked)."""
import hashlib
import hmac
import ipaddress
import time
from pathlib import Path

import httpx
import pytest
import respx

from archtwin.common import egress
from archtwin.connectors import webhooks
from archtwin.connectors.adapters.github import GitHubConnector
from archtwin.connectors.adapters.otel_servicegraph import OtelServiceGraphConnector
from archtwin.connectors.analyzers import python_code
from archtwin.connectors.analyzers.repo import analyze_repository


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda host: [ipaddress.ip_address("140.82.112.5")])


def sig(secret: str, msg: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


# ------------------------------------------------------------------ webhooks (AT-WORK_CONNECTORS-001 invalid signature)
class TestWebhookVerify:
    body = b'{"ref":"refs/heads/main","after":"abc"}'

    def test_github_valid(self):
        h = {"x-hub-signature-256": sig("s3", self.body), "x-github-delivery": "d-1"}
        assert webhooks.verify("github", "s3", h, self.body) == "d-1"

    @pytest.mark.parametrize("h", [{}, {"x-hub-signature-256": "sha256=00"}, {"x-hub-signature-256": sig("other", body)}])
    def test_github_bad_signature_rejected(self, h):
        with pytest.raises(webhooks.Rejected) as e:
            webhooks.verify("github", "s3", {**h, "x-github-delivery": "d"}, self.body)
        assert e.value.status == 401

    def test_tampered_body_rejected(self):
        h = {"x-hub-signature-256": sig("s3", self.body), "x-github-delivery": "d-1"}
        with pytest.raises(webhooks.Rejected):
            webhooks.verify("github", "s3", h, self.body + b" ")

    def test_generic_replay_window(self):
        now = time.time()
        ts = str(int(now))
        h = {"x-archtwin-timestamp": ts, "x-archtwin-signature": sig("k", ts.encode() + b"." + self.body), "x-archtwin-delivery": "x"}
        assert webhooks.verify("git", "k", h, self.body, now=now) == "x"
        with pytest.raises(webhooks.Rejected, match="stale"):
            webhooks.verify("git", "k", h, self.body, now=now + webhooks.REPLAY_WINDOW_S + 5)

    def test_no_secret_means_not_configured(self):
        with pytest.raises(webhooks.Rejected) as e:
            webhooks.verify("github", "", {"x-hub-signature-256": sig("", self.body)}, self.body)
        assert e.value.status == 404

    def test_missing_delivery_id(self):
        with pytest.raises(webhooks.Rejected) as e:
            webhooks.verify("github", "s3", {"x-hub-signature-256": sig("s3", self.body)}, self.body)
        assert e.value.status == 400


# ------------------------------------------------------------------ Kafka producer/consumer detection (task 3.3)
def test_kafka_detection(tmp_path: Path):
    f = tmp_path / "svc.py"
    f.write_text('''
from confluent_kafka import Consumer, Producer
p = Producer({"bootstrap.servers": "kafka:9092"})
p.produce("orders.created", value=b"x")
p.produce(topic_name, value=b"dynamic is never guessed")
c = Consumer({"bootstrap.servers": "kafka:9092", "group.id": "billing"})
c.subscribe(["orders.created", "orders.cancelled"])
from kafka import KafkaConsumer
k = KafkaConsumer("audit.log", group_id="auditor")
''')
    m = python_code.parse_module("svc", f, False)
    got = sorted((u.direction, u.topic) for u in m.kafka)
    assert ("publishes", "orders.created") in got
    assert ("consumes", "orders.created") in got and ("consumes", "orders.cancelled") in got and ("consumes", "audit.log") in got
    assert ("group", "billing") in got and ("group", "auditor") in got
    assert not any(t == "topic_name" for _, t in got)


def test_fixture_repo_ground_truth():
    """Static recall/precision on the labelled shop fixture (phase-02 tasks 0.2 / 3.4): compose + code -> expected topology."""
    import yaml
    root = Path(__file__).resolve().parents[4] / "fixtures" / "shop"
    gt = yaml.safe_load((root / "ground-truth.yaml").read_text())
    sysn = gt["system"]
    r = analyze_repository(root, "wt", sysn)

    def key(x):
        return x if ":" in x else f"container:{sysn}/{x}"
    expected = {f"{key(s)}|{k}|{key(t)}" for s, k, t in gt["static_edges"]}
    got = {o.subject_key for o in r.observations if o.subject_kind == "edge" and o.kind in ("calls", "writes", "publishes", "consumes")
           and o.attributes.get("target", "").split("/")[-1] not in ("otel-collector",)}
    missing = expected - got
    assert not missing, missing                                     # recall 100% on labelled edges
    business = {e for e in got if not e.endswith(("/kafka", "/schema-registry")) and "prometheus" not in e and "schema-init" not in e
                and "name:" not in e}                                   # name: refs are resolved (or dropped) by the graph builder
    assert business <= expected, business - expected                # precision: no invented application edges
    eps = {(o.attributes["source"].split("/")[-1], o.attributes["target"].split("/", 2)[-1]) for o in r.observations if o.kind == "exposes"}
    for svc, routes in gt["endpoints"].items():
        assert {(svc, rt) for rt in routes} <= eps, (svc, routes)
    nodes = {o.subject_key for o in r.observations if o.subject_kind == "node" and o.kind == "container"}
    assert {key(c) for c in gt["containers"]} == nodes


# ------------------------------------------------------------------ OTel service graph (task 4.3)
PROM = "http://prometheus.example:9090"


def _vec(rows):
    return {"status": "success", "data": {"resultType": "vector", "result": [{"metric": m, "value": [0, str(v)]} for m, v in rows]}}


@respx.mock
async def test_otel_servicegraph_edges():
    def handler(request: httpx.Request):
        q = request.url.params["query"]
        if "failed_total" in q:
            return httpx.Response(200, json=_vec([({"client": "web", "server": "orders"}, 3)]))
        if "histogram_quantile" in q:
            return httpx.Response(200, json=_vec([({"client": "web", "server": "orders"}, 0.120)]))
        return httpx.Response(200, json=_vec([({"client": "web", "server": "orders"}, 300),
                                              ({"client": "orders", "server": "orders", "connection_type": "database"}, 90),
                                              ({"client": "orders", "server": "billing", "connection_type": "messaging_system"}, 50),
                                              ({"client": "web", "server": "unknown", "connection_type": "virtual_node"}, 5)]))
    respx.get(url__startswith=f"{PROM}/api/v1/query").mock(side_effect=handler)
    r = await OtelServiceGraphConnector().scan({"prometheus_url": PROM, "system": "shop", "window": "5m",
                                                "service_map": {"web": "shop-web"}, "peer_map": {"orders": "orders-db"}}, {}, None)
    e = {o.subject_key: o for o in r.observations if o.subject_kind == "edge"}
    call = e["container:shop/shop-web|calls|container:shop/orders"]
    assert call.origin == "runtime" and call.attributes["requests"] == 300 and call.attributes["errors"] == 3
    assert call.attributes["p95_ms"] == 120.0 and call.attributes["window"] == "5m"
    assert "container:shop/orders|writes|container:shop/orders-db" in e
    assert "container:shop/orders|publishes|container:shop/billing" in e
    assert not any("unknown" in k for k in e)                          # unknown peers are never invented
    assert r.warnings and "unmapped" in r.warnings[0]
    assert r.coverage["prefixes"] == []                                # trace absence is not proof of absence


@respx.mock
async def test_otel_rejects_bad_window():
    with pytest.raises(ValueError):
        await OtelServiceGraphConnector().scan({"prometheus_url": PROM, "window": "1;drop"}, {}, None)


# ------------------------------------------------------------------ GitHub (tasks 3.1 / 6.1 / 6.3)
API = "https://api.github.com"


@respx.mock
async def test_github_test_warns_on_write_scopes():
    respx.get(f"{API}/user").mock(return_value=httpx.Response(200, json={"login": "u"}, headers={"x-oauth-scopes": "repo, read:org"}))
    respx.get(f"{API}/repos/o/r").mock(return_value=httpx.Response(200, json={"private": False, "default_branch": "main",
                                                                             "permissions": {"admin": True, "push": True, "pull": True}}))
    t = await GitHubConnector().test({"repos": ["o/r"]}, {"token": "ghp_x"})
    assert t.ok
    assert any("write/admin scopes" in w for w in t.warnings) and any("push/administer" in w for w in t.warnings)
    assert "ghp_x" not in str(t.details) + str(t.warnings)


async def test_github_rejects_bad_repo_names():
    t = await GitHubConnector().test({"repos": ["../etc/passwd"]}, {})
    assert not t.ok


@respx.mock
async def test_github_scan_work_items_and_closing_keywords():
    respx.get(f"{API}/repos/o/r").mock(return_value=httpx.Response(200, json={
        "default_branch": "main", "clone_url": "https://github.com/o/r.git", "html_url": "https://github.com/o/r", "visibility": "public"}))
    respx.get(f"{API}/repos/o/r/commits/main").mock(return_value=httpx.Response(200, json={"sha": "a" * 40}))
    respx.get(url__startswith=f"{API}/repos/o/r/branches").mock(return_value=httpx.Response(200, json=[
        {"name": "main", "commit": {"sha": "a" * 40}, "protected": True}, {"name": "feat", "commit": {"sha": "b" * 40}}]))
    respx.get(url__startswith=f"{API}/repos/o/r/issues").mock(return_value=httpx.Response(200, json=[
        {"number": 7, "title": "Checkout fails", "state": "open", "labels": [{"name": "bug"}], "html_url": "u7", "user": {"login": "a"}},
        {"number": 8, "title": "a PR shows up here too", "pull_request": {}, "state": "open"}]))
    respx.get(url__startswith=f"{API}/repos/o/r/pulls").mock(return_value=httpx.Response(200, json=[
        {"number": 8, "title": "Fix checkout", "body": "Fixes #7 and refs #9", "state": "closed", "merged_at": "2026-11-01T00:00:00Z",
         "head": {"ref": "feat", "sha": "b" * 40}, "base": {"ref": "main"}, "html_url": "u8", "user": {"login": "b"}}]))
    r = await GitHubConnector().scan({"repos": ["o/r"], "analyze_code": False}, {}, None)
    keys = {o.subject_key: o for o in r.observations}
    assert keys["work-item:github/o/r#7"].origin == "issue" and keys["work-item:github/o/r#7"].attributes["labels"] == ["bug"]
    assert keys["work-item:github/o/r#8"].attributes["type"] == "pull_request"
    assert "work-item:github/o/r#8|implements|work-item:github/o/r#7" in keys
    assert not any(k.endswith("#9") for k in keys)                  # "refs #9" is not a closing keyword
    assert r.revision == "a" * 40 and r.stats["issues"] == 1 and r.stats["pull_requests"] == 1


def test_github_has_no_write_calls():
    import inspect

    import archtwin.connectors.adapters.github as gh
    src = inspect.getsource(gh)
    for verb in (".post(", ".put(", ".patch(", ".delete(", "method=\"POST\""):
        assert verb not in src


# ------------------------------------------------------------------ L2 roll-up of messaging through the broker
def test_l2_rolls_topic_edges_up_to_broker_and_groups_one_shots():
    from archtwin.diagrams.views import system_view

    def n(key, kind, **a):
        return key, {"key": key, "kind": kind, "name": key.rsplit("/", 1)[-1], "attributes": a, "origins": ["static"], "evidence": []}

    def e(s, k, t, **a):
        return f"{s}|{k}|{t}", {"key": f"{s}|{k}|{t}", "kind": k, "source": s, "target": t, "attributes": a, "origins": ["static"], "confidence": 1}
    c = "container:shop/"
    nodes = dict([n("system:shop", "software-system"), n(f"{c}orders", "container", subtype="service"),
                  n(f"{c}billing", "container", subtype="service"), n(f"{c}kafka", "container", subtype="queue"),
                  n(f"{c}kafka-init", "container", subtype="queue", one_shot=True, one_shot_exited_ok=True, state="exited"),
                  n("kafka-topic:shop/kafka/orders.created", "kafka-topic")])
    edges = dict([*(e("system:shop", "contains", k) for k in nodes if k.startswith(c)),
                  e(f"{c}kafka", "contains", "kafka-topic:shop/kafka/orders.created"),
                  e(f"{c}orders", "calls", f"{c}kafka", protocol="tcp"),
                  e(f"{c}orders", "publishes", "kafka-topic:shop/kafka/orders.created"),
                  e(f"{c}billing", "consumes", "kafka-topic:shop/kafka/orders.created")])
    v = system_view({"nodes": nodes, "edges": edges}, "shop", set())
    by = {(x["source"], x["target"]): x for x in v["edges"]}
    assert by[(f"{c}orders", f"{c}kafka")]["label"] == "publishes · orders.created"
    assert by[(f"{c}billing", f"{c}kafka")]["label"] == "consumes · orders.created"
    init = next(x for x in v["nodes"] if x["id"] == f"{c}kafka-init")
    assert init["state"] == "completed"


def test_same_service_name_in_two_compose_projects(tmp_path: Path):
    """A repo may hold several compose projects; `api` in one must not overwrite `api` in the other."""
    for proj in ("alpha", "beta"):
        d = tmp_path / proj
        (d / "svc" / "pkg").mkdir(parents=True)
        (d / "svc" / "pkg" / "__init__.py").write_text("")
        (d / "svc" / "pkg" / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n@app.get('/x')\ndef x(): ...\n")
        (d / "compose.yaml").write_text(f"name: {proj}\nservices:\n  api:\n    build: ./svc\n    command: [uvicorn, 'pkg.app:app']\n")
    r = analyze_repository(tmp_path, "wt", "repo")
    eps = {o.subject_key for o in r.observations if o.kind == "api-endpoint"}
    assert {"endpoint:alpha/api/GET /x", "endpoint:beta/api/GET /x"} <= eps

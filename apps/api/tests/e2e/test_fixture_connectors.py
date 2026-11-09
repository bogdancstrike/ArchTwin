"""M1 connectors end to end against the live shop fixture (make fixtures-up). Skipped when the fixture is not running.

Covers: MySQL + PostgreSQL catalogs, Kafka (topics, groups, lag, Schema Registry), OTel service graph via Prometheus, Docker
runtime, the static analyzer on the fixture repo, identity reconciliation across all of them, and signed webhooks
(valid, duplicate delivery, duplicate commit, bad signature -> nothing stored).
"""
import hashlib
import hmac
import json
import os
import uuid

import httpx
import pytest

from tests.e2e.conftest import API, wait

PROM_HOST = os.environ.get("ARCHTWIN_FIXTURE_PROMETHEUS", "http://127.0.0.1:9390")
SYS = "archtwin-fixtures"
C = f"container:{SYS}/"


def _fixture_up() -> bool:
    try:
        return httpx.get(f"{PROM_HOST}/-/ready", timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True, scope="module")
def _require_target():          # probed lazily (not at import) so unit-test collection never touches the network
    if not _fixture_up():
        pytest.skip("shop fixture not running (make fixtures-up)")


@pytest.fixture(scope="module")
def shop(users, run_id):
    admin = users["admin"]
    p = admin.ok("POST", "/projects", 201, json={"title": f"Shop fixture {run_id}", "purpose": "e2e: reference fixture", "tags": ["e2e", "fixture"]},
                 headers={"Idempotency-Key": f"shop-{run_id}"})
    pid = p["id"]
    specs = [
        ("git", "shop-repo", {"path": "/sources/archtwin/fixtures/shop", "name": SYS}, {"webhook_secret": "ARCHTWIN-CANARY-whsec"}),
        ("docker", "shop-runtime", {"endpoint": "http://docker-proxy:2375", "compose_projects": [SYS]}, None),
        ("postgresql", "orders-catalog", {"host": "orders-db", "port": 5432, "database": "orders", "username": "archtwin_catalog_ro",
                                          "schemas": ["public"], "system": SYS, "service": "orders-db"}, {"password": "catalog-ro"}),
        ("mysql", "inventory-catalog", {"host": "inventory-db", "port": 3306, "database": "inventory", "username": "archtwin_catalog_ro",
                                        "system": SYS, "service": "inventory-db"}, {"password": "catalog-ro"}),
        ("kafka", "shop-kafka", {"bootstrap_servers": "kafka:9092", "system": SYS, "service": "kafka",
                                 "schema_registry_url": "http://schema-registry:8081", "group_services": {"billing": "shop-billing"}}, None),
        ("otel_servicegraph", "shop-traces", {"prometheus_url": "http://prometheus:9090", "system": SYS, "window": "10m",
                                              "peer_map": {"orders": "orders-db", "inventory": "inventory-db"}}, None),
    ]
    cs = {}
    for kind, name, cfg, sec in specs:
        cs[kind] = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={"kind": kind, "name": name, "config": cfg, "secret": sec})
    return {"id": pid, "connectors": cs}


def _scan(admin, pid, cid, ref=None):
    admin.ok("POST", f"/projects/{pid}/connectors/{cid}/scan", 202, json={"ref": ref} if ref else {})
    return wait(lambda: next((s for s in admin.ok("GET", f"/projects/{pid}/scans", params={"connector_id": cid})
                              if s["status"] in ("complete", "partial", "failed")), None), what=f"scan {cid}")


def test_connector_tests_report_scopes_without_secrets(users, shop):
    admin, pid = users["admin"], shop["id"]
    for kind, c in shop["connectors"].items():
        t = admin.ok("POST", f"/projects/{pid}/connectors/{c['id']}/test")
        assert t["ok"], (kind, t)
        assert "catalog-ro" not in json.dumps(t) and "CANARY" not in json.dumps(t)
    k = admin.ok("POST", f"/projects/{pid}/connectors/{shop['connectors']['kafka']['id']}/test")
    assert k["details"]["topics"] >= 2 and k["details"]["schema_subjects"] >= 1
    my = admin.ok("POST", f"/projects/{pid}/connectors/{shop['connectors']['mysql']['id']}/test")
    assert my["warnings"] == [], "REFERENCES-only account must not be flagged as over-privileged"


def test_scans_and_reconciliation(users, shop):
    admin, pid = users["admin"], shop["id"]
    for kind, c in shop["connectors"].items():
        s = _scan(admin, pid, c["id"])
        assert s["status"] == "complete", (kind, s)
    def ready():
        g = admin.ok("GET", f"/projects/{pid}/architecture")
        ok = g.get("snapshot") and any(n["kind"] == "kafka-topic" for n in g["nodes"].values()) and any(
            "runtime" in e["origins"] for e in g["edges"].values() if e["kind"] == "calls")
        return g if ok else None
    g = wait(ready, timeout=120, what="snapshot with all connectors")
    nodes, edges = g["nodes"], g["edges"]

    # data topology: tables from both engines, sensitive columns flagged
    assert f"table:{SYS}/orders-db/orders/public.orders" in nodes
    stock = nodes[f"table:{SYS}/inventory-db/inventory/inventory.stock"]
    assert stock["kind"] == "table"
    assert f"table:{SYS}/inventory-db/inventory/inventory.stock|references|table:{SYS}/inventory-db/inventory/inventory.warehouses" in edges
    assert nodes[f"table:{SYS}/orders-db/orders/public.customers"].get("sensitive") is True       # email

    # Kafka: the topic the code publishes to is the SAME element the cluster reports (static + runtime origins merge)
    topic = nodes[f"kafka-topic:{SYS}/kafka/orders.created"]
    assert {"static", "runtime"} <= set(topic["origins"]), topic["origins"]
    assert topic["attributes"]["partitions"] == 3 or topic.get("by_origin", {}).get("runtime", {}).get("partitions") == 3
    assert f"kafka-topic:{SYS}/kafka/inventory.audit" in nodes                     # runtime-only topic (no code uses it)
    assert f"{C}shop-orders|publishes|kafka-topic:{SYS}/kafka/orders.created" in edges
    cons = edges[f"{C}shop-billing|consumes|kafka-topic:{SYS}/kafka/orders.created"]
    assert {"static", "runtime"} <= set(cons["origins"])
    assert f"kafka-topic:{SYS}/kafka/orders.created|implements|event-schema:{SYS}/kafka/orders.created-value" in edges

    # OTel service graph: runtime calls confirm the statically declared wiring
    call = edges[f"{C}shop-web|calls|{C}shop-orders"]
    assert {"static", "runtime"} <= set(call["origins"]), call["origins"]
    assert {"static", "runtime"} <= set(edges[f"{C}shop-inventory|writes|{C}inventory-db"]["origins"])

    # Docker runtime: the fixture containers are running and keyed like the compose analysis
    assert "runtime" in nodes[f"{C}shop-billing"]["origins"] and "static" in nodes[f"{C}shop-billing"]["origins"]


def _push(secret: str, sha: str, delivery: str, tamper: bool = False):
    body = json.dumps({"ref": "refs/heads/main", "after": sha, "repository": {"default_branch": "main"}, "commits": [{}]}).encode()
    import time
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    return body + (b" " if tamper else b""), {"X-ArchTwin-Timestamp": ts, "X-ArchTwin-Signature": sig, "X-ArchTwin-Delivery": delivery,
                                              "X-ArchTwin-Event": "push", "Content-Type": "application/json"}


def test_signed_webhooks_dedupe_and_reject(users, shop):
    admin, pid = users["admin"], shop["id"]
    c = shop["connectors"]["git"]
    info = admin.ok("GET", f"/projects/{pid}/connectors/{c['id']}/webhook")
    assert info["enabled"] and info["url"].endswith(f"/webhooks/{info['url'].split('/webhooks/')[1]}")
    url = f"{API}/webhooks/{info['url'].split('/webhooks/')[1]}"
    head = admin.ok("POST", f"/projects/{pid}/connectors/{c['id']}/test")["details"]["head"]
    secret = "ARCHTWIN-CANARY-whsec"
    d1 = uuid.uuid4().hex

    body, h = _push(secret, head, d1, tamper=True)                      # tampered body: rejected, nothing stored
    r = httpx.post(url, content=body, headers=h, timeout=20)
    assert r.status_code == 401 and "CANARY" not in r.text
    assert not any(x["delivery_id"] == d1 for x in admin.ok("GET", f"/projects/{pid}/connectors/{c['id']}/webhook")["recent"])

    body, h = _push(secret, head, d1)
    first = httpx.post(url, content=body, headers=h, timeout=20).json()
    assert first["outcome"] in ("scan_queued", "duplicate_commit"), first
    again = httpx.post(url, content=body, headers=h, timeout=20).json()   # same delivery redelivered
    assert again["duplicate"] is True
    body, h = _push(secret, head, uuid.uuid4().hex)                      # new delivery, same commit
    assert httpx.post(url, content=body, headers=h, timeout=20).json()["outcome"] == "duplicate_commit"
    scans = [s for s in admin.ok("GET", f"/projects/{pid}/scans", params={"connector_id": c["id"]}) if s["ref"] == head]
    assert len(scans) == 1, "one extraction per commit"

    body, h = _push("wrong-secret", head, uuid.uuid4().hex)
    assert httpx.post(url, content=body, headers=h, timeout=20).status_code == 401
    other = f"{API}/webhooks/{uuid.uuid4()}/{pid}/{c['id']}"             # wrong org in path: same opaque rejection
    body, h = _push(secret, head, uuid.uuid4().hex)
    assert httpx.post(other, content=body, headers=h, timeout=20).status_code == 404


def test_flags_gate_new_connectors(users, shop):
    admin, pid = users["admin"], shop["id"]
    admin.ok("PUT", "/flags/connector.kafka", json={"scope_kind": "project", "scope_id": pid, "value": False, "reason": "e2e"})
    try:
        r = admin.post(f"/projects/{pid}/connectors/{shop['connectors']['kafka']['id']}/scan", json={})
        assert r.status_code == 404 and r.json()["code"] == "AT-FEATURE-DISABLED"
    finally:
        admin.ok("PUT", "/flags/connector.kafka", json={"scope_kind": "project", "scope_id": pid, "value": True, "reason": "e2e"})

#!/usr/bin/env python3
"""Create (idempotently) the "Shop (reference fixture)" demo project with all M1 connectors and scan them.

Needs the app stack (`make up`) and the fixture (`make fixtures-up`). Uses the dev admin account through the public API only.
  python3 scripts/demo-fixture.py [--api http://localhost:8200/api/v1] [--user admin --password admin]
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

TITLE = "Shop (reference fixture)"
SYS = "archtwin-fixtures"
CONNECTORS = [
    ("git", "shop-repo", {"path": "/sources/archtwin/fixtures/shop", "name": SYS}, None),
    ("docker", "shop-runtime", {"endpoint": "http://docker-proxy:2375", "compose_projects": [SYS]}, None),
    ("otel_servicegraph", "shop-traces", {"prometheus_url": "http://prometheus:9090", "system": SYS, "window": "15m",
                                          "peer_map": {"orders": "orders-db", "inventory": "inventory-db"}}, None),
    ("postgresql", "orders-catalog", {"host": "orders-db", "port": 5432, "database": "orders", "username": "archtwin_catalog_ro",
                                      "schemas": ["public"], "system": SYS, "service": "orders-db"}, {"password": "catalog-ro"}),
    ("mysql", "inventory-catalog", {"host": "inventory-db", "port": 3306, "database": "inventory", "username": "archtwin_catalog_ro",
                                    "system": SYS, "service": "inventory-db"}, {"password": "catalog-ro"}),
    ("kafka", "shop-kafka", {"bootstrap_servers": "kafka:9092", "system": SYS, "service": "kafka",
                             "schema_registry_url": "http://schema-registry:8081", "group_services": {"billing": "shop-billing"}}, None),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8200/api/v1")
    ap.add_argument("--keycloak", default="http://localhost:8280/realms/archtwin/protocol/openid-connect/token")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="admin")
    a = ap.parse_args()
    tok = json.load(urllib.request.urlopen(urllib.request.Request(a.keycloak, data=urllib.parse.urlencode(
        {"grant_type": "password", "client_id": "archtwin-cli", "username": a.user, "password": a.password}).encode())))["access_token"]

    def call(method, path, body=None):
        req = urllib.request.Request(a.api + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.load(r)

    p = next((x for x in call("GET", "/projects") if x["title"] == TITLE), None)
    if not p:
        p = call("POST", "/projects", {"title": TITLE, "purpose": "OTel-instrumented shop: web, orders, inventory, billing, Kafka, PostgreSQL, MySQL",
                                        "tags": ["fixture", "demo"], "environments": ["dev"]})
    pid = p["id"]
    have = {c["name"]: c for c in call("GET", f"/projects/{pid}/connectors")}
    for kind, name, cfg, sec in CONNECTORS:
        c = have.get(name) or call("POST", f"/projects/{pid}/connectors", {"kind": kind, "name": name, "config": cfg, "secret": sec})
        call("POST", f"/projects/{pid}/connectors/{c['id']}/scan", {})
        print(f"  scan queued: {name} ({kind})")
    for _ in range(60):
        scans = call("GET", f"/projects/{pid}/scans")
        if scans and all(s["status"] not in ("queued", "running") for s in scans[:len(CONNECTORS)]):
            break
        time.sleep(2)
    print(f"{TITLE}: http://localhost:3200/projects/{pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

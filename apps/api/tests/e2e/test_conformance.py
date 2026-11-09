"""Guided baselines and decision conformance on the live stack: baseline from the latest architecture in one step (four-eyes
for everyone, audited self-approval for org admins), ADR conformance rules amended after acceptance by approvers only, and
the drift engine raising a finding that cites the violated decision."""
import pytest

from tests.e2e.conftest import wait

pytestmark = pytest.mark.e2e

SAMPLE = "/sources/archtwin/apps/api/tests/fixtures/sample_repo"


@pytest.fixture(scope="module")
def proj(users, run_id):
    admin = users["admin"]
    p = admin.ok("POST", "/projects", 201, json={"title": f"Conformance {run_id}", "purpose": "e2e: baselines + ADR rules"})
    ids = {m["username"]: m["id"] for m in admin.ok("GET", "/org/users")}
    for u, role in (("alice", "architect"), ("bob", "reviewer"), ("vera", "viewer")):
        admin.ok("PUT", f"/projects/{p['id']}/members", json={"user_id": ids[u], "role": role})
    c = admin.ok("POST", f"/projects/{p['id']}/connectors", 201, json={"kind": "git", "name": "sample", "config": {"path": SAMPLE, "name": "shop"}})
    admin.ok("POST", f"/projects/{p['id']}/connectors/{c['id']}/scan", 202, json={})
    wait(lambda: admin.ok("GET", f"/projects/{p['id']}/snapshots"), what="snapshot")
    return p


def test_guided_baseline(users, proj):
    alice, bob, vera, admin = users["alice"], users["bob"], users["vera"], users["admin"]
    pid = proj["id"]
    st = alice.ok("GET", f"/projects/{pid}/baselines/status")
    assert st["state"] == "none" and st["can_propose"] and not st["can_self_approve"] and st["latest_snapshot"]
    assert vera.post(f"/projects/{pid}/baselines/from-latest", json={}).status_code == 403
    b = alice.ok("POST", f"/projects/{pid}/baselines/from-latest", 201, json={"approve_now": True})   # not an admin: stays proposed
    assert b["status"] == "proposed"
    assert alice.ok("POST", f"/projects/{pid}/baselines/from-latest", 201, json={})["id"] == b["id"]   # idempotent per snapshot
    st = bob.ok("GET", f"/projects/{pid}/baselines/status")
    assert st["state"] == "pending" and st["pending"][0]["can_approve"] and not st["pending"][0]["mine"]
    assert alice.ok("GET", f"/projects/{pid}/baselines/status")["pending"][0]["can_approve"] is False   # four-eyes
    bob.ok("POST", f"/projects/{pid}/baselines/{b['id']}/approve", json={"note": ""})
    st = admin.ok("GET", f"/projects/{pid}/baselines/status")
    assert st["state"] == "approved" and st["approved"]["id"] == b["id"] and st["outdated"] is False and st["can_self_approve"]


def test_adr_conformance_rules_raise_drift(users, proj):
    alice, bob, vera = users["alice"], users["bob"], users["vera"]
    pid = proj["id"]
    rule = {"type": "forbid", "from": "container:shop/api", "to": "container:shop/db", "relation": "writes",
            "description": "the API reads through the worker"}
    a = alice.ok("POST", f"/projects/{pid}/adrs", 201, json={"title": "API does not write the database", "context": "CQRS",
                                                           "decision_outcome": "writes go through the worker", "constraints": [rule, {"type": "bogus"}]})
    assert [c["type"] for c in alice.ok("GET", f"/projects/{pid}/adrs/{a['id']}")["current"]["content"]["constraints"]] == ["forbid"]
    bob.ok("POST", f"/projects/{pid}/adrs/{a['id']}/accept", json={})
    assert alice.put(f"/projects/{pid}/adrs/{a['id']}", json={"title": "x" * 5}).status_code == 409               # accepted: immutable
    assert vera.put(f"/projects/{pid}/adrs/{a['id']}/constraints", json={"constraints": [rule]}).status_code == 403
    amended = bob.ok("PUT", f"/projects/{pid}/adrs/{a['id']}/constraints", json={"constraints": [
        rule, {"type": "only-via", "to": "container:shop/db", "via": "container:shop/worker", "allow": "container:shop/migrate"}]})
    assert amended["status"] == "accepted" and len(amended["current"]["content"]["constraints"]) == 2
    alice.ok("POST", f"/projects/{pid}/drift/evaluate")
    found = {f["rule_id"]: f for f in alice.ok("GET", f"/projects/{pid}/drift?status=open")}
    assert "DR-ADR-FORBID-001" in found and found["DR-ADR-FORBID-001"]["severity"] == "high"
    assert found["DR-ADR-FORBID-001"]["expected"]["adr_title"] == "API does not write the database"
    assert "DR-ADR-VIA-001" in found                                     # the API reaches the database without the worker

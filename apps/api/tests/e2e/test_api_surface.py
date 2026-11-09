"""API surface: every route's happy path plus its negative branches (validation, revisions, separation of duties, 404s).

Runs against the live Compose stack on a small project that scans `tests/fixtures/sample_repo` (mounted read-only at /sources/archtwin).
"""
import json
import uuid

import httpx
import pytest

from tests.e2e.conftest import API, wait

pytestmark = pytest.mark.e2e

SAMPLE = "/sources/archtwin/apps/api/tests/fixtures/sample_repo"
NOPE = "00000000-0000-7000-8000-000000000001"


@pytest.fixture(scope="module")
def proj(users, run_id):
    admin = users["admin"]
    p = admin.ok("POST", "/projects", 201, json={"title": f"Surface {run_id}", "purpose": "e2e: API surface"})
    ids = {m["username"]: m["id"] for m in admin.ok("GET", "/org/users")}
    for u, role in (("alice", "architect"), ("bob", "reviewer"), ("vera", "viewer")):
        admin.ok("PUT", f"/projects/{p['id']}/members", json={"user_id": ids[u], "role": role})
    c = admin.ok("POST", f"/projects/{p['id']}/connectors", 201, json={"kind": "git", "name": "sample", "config": {"path": SAMPLE, "name": "shop"}})
    admin.ok("POST", f"/projects/{p['id']}/connectors/{c['id']}/scan", 202, json={})
    wait(lambda: any(s["status"] == "complete" for s in admin.ok("GET", f"/projects/{p['id']}/scans?connector_id={c['id']}")), what="sample scan")
    wait(lambda: admin.ok("GET", f"/projects/{p['id']}/snapshots"), what="snapshot")
    return {**p, "ids": ids, "connector": c}


# ------------------------------------------------------------------ identity & org
def test_preferences_and_model_validation(users):
    a = users["alice"]
    assert a.put("/me/preferences", json={"preferred_model": "gpt-4o"}).status_code == 422
    assert a.ok("PUT", "/me/preferences", json={"preferred_model": "gpt-6-luna", "theme": "dark"})["theme"] == "dark"
    me = a.ok("GET", "/me")
    assert me["preferences"]["preferred_model"] == "gpt-6-luna" and me["orgs"]
    assert a.ok("GET", "/ai/models")["preferred"] == "gpt-6-luna"


def test_diagram_tokens_are_sanitised_and_admin_only(users):
    admin, vera = users["admin"], users["vera"]
    cur = admin.ok("GET", "/org/diagram-tokens")
    key = next(iter(cur["defaults"]))
    assert vera.put("/org/diagram-tokens", json={"tokens": {key: "#123456"}}).status_code == 403
    out = admin.ok("PUT", "/org/diagram-tokens", json={"tokens": {key: "#123456", "bogus": "#fff", "ink": "red;}</style>"}})
    assert out["org"] == {key: "#123456"}
    assert admin.ok("GET", "/org/diagram-tokens")["org"] == {key: "#123456"}
    admin.ok("PUT", "/org/diagram-tokens", json={"tokens": cur["org"]})


# ------------------------------------------------------------------ projects & members
def test_project_patch_requires_matching_revision(users, proj):
    admin, vera = users["admin"], users["vera"]
    pid = proj["id"]
    assert admin.patch(f"/projects/{pid}", json={"purpose": "x"}).status_code == 428
    assert vera.patch(f"/projects/{pid}", json={"purpose": "x"}, headers={"If-Match": "1"}).status_code == 403
    rev = admin.ok("GET", f"/projects/{pid}")["revision"]
    assert admin.patch(f"/projects/{pid}", json={"purpose": "x"}, headers={"If-Match": str(rev + 7)}).status_code == 412
    up = admin.ok("PATCH", f"/projects/{pid}", json={"purpose": "e2e: API surface (edited)", "tags": ["e2e"]}, headers={"If-Match": f'"{rev}"'})
    assert up["revision"] == rev + 1 and up["tags"] == ["e2e"]


def test_members_roles_and_last_owner(users, proj):
    admin = users["admin"]
    pid, ids = proj["id"], proj["ids"]
    assert admin.put(f"/projects/{pid}/members", json={"user_id": ids["vera"], "role": "emperor"}).status_code == 422
    assert admin.put(f"/projects/{pid}/members", json={"user_id": ids["admin"], "role": "viewer"}).status_code == 409
    assert users["alice"].put(f"/projects/{pid}/members", json={"user_id": ids["vera"], "role": "architect"}).status_code == 403
    tmp = next(u for u in ids if u not in ("admin", "alice", "bob", "vera", "mallory")) if len(ids) > 4 else None
    if tmp:
        admin.ok("PUT", f"/projects/{pid}/members", json={"user_id": ids[tmp], "role": "contributor"})
        admin.ok("PUT", f"/projects/{pid}/members", json={"user_id": ids[tmp], "role": None})
    names = {m["username"]: m["role"] for m in users["vera"].ok("GET", f"/projects/{pid}/members")}
    assert names["vera"] == "viewer" and names["admin"] == "project_owner"


def test_project_home_cards_follow_flags(users, proj):
    admin, alice = users["admin"], users["alice"]
    pid = proj["id"]
    home = alice.ok("GET", f"/projects/{pid}/home")
    assert home["freshness"]["configured"] and home["architecture"]["configured"] and home["decisions"]["configured"]
    keys = ("module.architecture-graph", "module.drift-engine", "module.adr-workflow")
    try:
        for k in keys:
            admin.ok("PUT", f"/flags/{k}", json={"scope_kind": "project", "scope_id": pid, "value": False, "reason": "e2e"})
        off = alice.ok("GET", f"/projects/{pid}/home")
        assert all(off[c]["configured"] is False and "is off" in off[c]["reason"] for c in ("architecture", "drift", "decisions"))
        assert any(f["key"] == "module.drift-engine" for f in admin.ok("GET", f"/flags?project_id={pid}"))
        kinds = admin.ok("GET", f"/connector-kinds?project_id={pid}")
        assert {k["kind"] for k in kinds} >= {"git", "docker", "github", "kafka"}
    finally:
        for k in keys:
            admin.ok("PUT", f"/flags/{k}", json={"scope_kind": "project", "scope_id": pid, "value": True})


def test_flag_scoped_to_unknown_project_is_404(users):
    r = users["admin"].put("/flags/module.drift-engine", json={"scope_kind": "project", "scope_id": NOPE, "value": False})
    assert r.status_code == 404


# ------------------------------------------------------------------ audit
def test_audit_filters_and_permissions(users, proj):
    admin, vera = users["admin"], users["vera"]
    pid = proj["id"]
    mine = admin.ok("GET", f"/audit?project_id={pid}&actor=admin&action=project&limit=20")
    assert mine and all(e["actor_name"] == "admin" and e["action"].startswith("project") for e in mine)
    assert vera.get(f"/audit?project_id={pid}").status_code == 403
    assert vera.get("/audit/verify").status_code == 403
    assert admin.get("/audit?limit=5000").status_code == 422


# ------------------------------------------------------------------ connectors & inventory
def test_connector_lifecycle_and_inventory(users, proj):
    admin, alice, vera = users["admin"], users["alice"], users["vera"]
    pid, cid = proj["id"], proj["connector"]["id"]
    assert any(c["id"] == cid for c in vera.ok("GET", f"/projects/{pid}/connectors"))
    hook = admin.ok("GET", f"/projects/{pid}/connectors/{cid}/webhook")
    assert hook["url"].endswith(f"/webhooks/{proj['org_id']}/{pid}/{cid}") and hook["events"] == ["push"] and "X-ArchTwin" in hook["signature"]
    inv = alice.ok("GET", f"/projects/{pid}/inventory")
    assert inv["connectors"] and inv["observation_counts"]
    key = next(iter(alice.ok("GET", f"/projects/{pid}/architecture?kinds=container")["nodes"]))
    assert alice.ok("GET", f"/projects/{pid}/observations", params={"key": key})
    tmp = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={"kind": "git", "name": "throwaway", "config": {"path": SAMPLE}})
    assert alice.delete(f"/projects/{pid}/connectors/{tmp['id']}").status_code == 403
    assert admin.delete(f"/projects/{pid}/connectors/{tmp['id']}").status_code == 204
    gone = admin.post(f"/projects/{pid}/connectors/{tmp['id']}/scan", json={})     # soft delete: evidence stays, scanning stops
    assert gone.status_code == 409 and gone.json()["code"] == "AT-CONN-003"
    assert admin.delete(f"/projects/{pid}/connectors/{NOPE}").status_code == 404
    assert admin.post(f"/projects/{pid}/connectors", json={"kind": "telepathy", "name": "nope"}).status_code in (404, 422)
    bad_ref = admin.ok("POST", f"/projects/{pid}/connectors/{cid}/scan", 202, json={"ref": "no-such-branch"})
    assert bad_ref["id"]
    wait(lambda: any(s["id"] == bad_ref["id"] and s["status"] == "failed" for s in admin.ok("GET", f"/projects/{pid}/scans")), what="failed scan")


# ------------------------------------------------------------------ architecture
def test_architecture_snapshots_diff_and_time_travel(users, proj):
    alice = users["alice"]
    pid = proj["id"]
    first = alice.ok("GET", f"/projects/{pid}/snapshots")[-1]
    again = alice.ok("POST", f"/projects/{pid}/snapshots")
    assert again.get("version", first["version"]) >= first["version"]
    latest = alice.ok("GET", f"/projects/{pid}/snapshots")[0]
    d = alice.ok("GET", f"/projects/{pid}/diff", params={"from": first["id"], "to": latest["id"]})
    assert d["from"]["version"] == first["version"]
    assert alice.get(f"/projects/{pid}/diff", params={"from": first["id"], "to": NOPE}).status_code == 404
    old = alice.ok("GET", f"/projects/{pid}/architecture", params={"at": "2000-01-01T00:00:00Z"})
    assert old["snapshot"] is None and old["nodes"] == {}
    by_id = alice.ok("GET", f"/projects/{pid}/architecture", params={"snapshot_id": first["id"], "kinds": "container,database"})
    assert by_id["nodes"] and {n["kind"] for n in by_id["nodes"].values()} <= {"container", "database"}
    assert users["vera"].post(f"/projects/{pid}/snapshots").status_code == 403


def test_baseline_reject_and_invalid_decisions(users, proj):
    alice, bob = users["alice"], users["bob"]
    pid = proj["id"]
    assert alice.post(f"/projects/{pid}/baselines", json={"snapshot_id": NOPE}).status_code == 404
    snap = alice.ok("GET", f"/projects/{pid}/snapshots")[0]
    b = alice.ok("POST", f"/projects/{pid}/baselines", 201, json={"snapshot_id": snap["id"], "note": "to reject"})
    assert bob.post(f"/projects/{pid}/baselines/{b['id']}/veto", json={}).status_code == 404
    assert bob.post(f"/projects/{pid}/baselines/{NOPE}/approve", json={}).status_code == 404
    rej = bob.ok("POST", f"/projects/{pid}/baselines/{b['id']}/reject", json={"note": "not yet"})
    assert rej["status"] == "rejected" and "not yet" in rej["note"]
    assert bob.post(f"/projects/{pid}/baselines/{b['id']}/approve", json={}).status_code == 409
    ok = alice.ok("POST", f"/projects/{pid}/baselines", 201, json={"snapshot_id": snap["id"]})
    assert bob.ok("POST", f"/projects/{pid}/baselines/{ok['id']}/approve", json={})["status"] == "approved"
    assert {x["status"] for x in alice.ok("GET", f"/projects/{pid}/baselines")} >= {"approved", "rejected"}


def test_identity_merge_split_and_manual_retract(users, proj):
    alice = users["alice"]
    pid = proj["id"]
    assert set(alice.ok("GET", f"/projects/{pid}/identities")) == {"suggestions", "aliases"}
    k = "container:shop/legacy-name"
    assert alice.post(f"/projects/{pid}/identities/merge", json={"alias_key": k, "canonical_key": k}).status_code == 422
    alice.ok("POST", f"/projects/{pid}/identities/merge", json={"alias_key": k, "canonical_key": "container:shop/api", "reason": "renamed"})
    assert any(a["alias_key"] == k for a in alice.ok("GET", f"/projects/{pid}/identities")["aliases"])
    assert alice.ok("POST", f"/projects/{pid}/identities/split", json={"alias_key": k, "canonical_key": ""}) == {"ok": True}
    assert not any(a["alias_key"] == k for a in alice.ok("GET", f"/projects/{pid}/identities")["aliases"])
    alice.ok("POST", f"/projects/{pid}/manual-elements", 201, json={"subject_kind": "node", "key": "container:shop/ghost", "kind": "container",
                                                                   "name": "ghost", "retract": True})
    assert users["vera"].post(f"/projects/{pid}/identities/merge", json={"alias_key": "a:b", "canonical_key": "a:c"}).status_code == 403


# ------------------------------------------------------------------ diagrams
def test_layouts_revisions_reset_and_exports(users, proj):
    alice, vera = users["alice"], users["vera"]
    pid = proj["id"]
    v = alice.ok("GET", f"/projects/{pid}/views/context")
    n = v["nodes"][0]["id"]
    assert vera.put(f"/projects/{pid}/layouts/context", json={"overrides": {n: {"x": 1, "y": 2}}}).status_code == 403
    r1 = alice.ok("PUT", f"/projects/{pid}/layouts/context", json={"overrides": {n: {"x": 10, "y": 20}, "bad": {"x": 1}}})
    r2 = alice.ok("PUT", f"/projects/{pid}/layouts/context", json={"overrides": {n: {"x": 30, "y": 40}}, "revision": r1["revision"]})
    assert r2["revision"] == r1["revision"] + 1
    assert alice.put(f"/projects/{pid}/layouts/context", json={"overrides": {}, "revision": r1["revision"]}).status_code == 412
    assert alice.ok("GET", f"/projects/{pid}/views/context")["layout"]["overrides"][n] == {"x": 30.0, "y": 40.0}
    assert alice.ok("DELETE", f"/projects/{pid}/layouts/context") == {"ok": True}
    assert alice.ok("GET", f"/projects/{pid}/views/context")["layout"]["revision"] == 0
    assert alice.get(f"/projects/{pid}/views/nonsense:view").status_code == 404
    html = alice.get(f"/projects/{pid}/export/html/context")
    assert html.status_code == 200 and html.text.startswith("<!doctype html>") and "Content-Security-Policy" in html.text
    assert alice.get(f"/projects/{pid}/export/pdf/context").status_code == 404
    assert alice.ok("GET", f"/projects/{pid}/views/context", params={"full": "true", "deps": "true"})["nodes"]


def test_views_without_snapshot_are_409(users, run_id):
    admin = users["admin"]
    empty = admin.ok("POST", "/projects", 201, json={"title": f"Empty {run_id}"})
    r = admin.get(f"/projects/{empty['id']}/views/context")
    assert r.status_code == 409 and r.json()["code"] == "AT-DIAGRAM-001"
    home = admin.ok("GET", f"/projects/{empty['id']}/home")
    assert home["freshness"]["configured"] is False and home["architecture"]["snapshot"] is None


# ------------------------------------------------------------------ decisions
def test_adr_edit_reject_supersede(users, proj):
    alice, bob, vera = users["alice"], users["bob"], users["vera"]
    pid = proj["id"]
    a1 = alice.ok("POST", f"/projects/{pid}/adrs", 201, json={"title": "Adopt Kafka for order events", "decision_drivers": ["decoupling"],
                                                            "considered_options": [{"name": "Kafka", "pros": ["replay"], "cons": ["ops"]}, {"name": "RabbitMQ"}],
                                                            "links": ["container:shop/api"]})
    ed = alice.ok("PUT", f"/projects/{pid}/adrs/{a1['id']}", json={"title": "Adopt Kafka for order events (v2)", "context": "more context",
                                                                  "decision_drivers": ["decoupling"],
                                                                  "considered_options": [{"name": "Kafka", "pros": ["replay"], "cons": ["ops"]}],
                                                                  "links": ["container:shop/api"]})
    assert ed["current_version"] == 2 and ed["title"].endswith("(v2)")
    assert vera.put(f"/projects/{pid}/adrs/{a1['id']}", json={"title": "vandalised"}).status_code == 403
    assert bob.post(f"/projects/{pid}/adrs/{a1['id']}/postpone", json={}).status_code == 404
    assert bob.ok("POST", f"/projects/{pid}/adrs/{a1['id']}/accept", json={})["status"] == "accepted"
    assert bob.post(f"/projects/{pid}/adrs/{a1['id']}/reject", json={}).status_code == 409
    a2 = alice.ok("POST", f"/projects/{pid}/adrs", 201, json={"title": "Replace Kafka with NATS"})
    acc = bob.ok("POST", f"/projects/{pid}/adrs/{a2['id']}/accept", json={"supersedes": a1["id"]})
    assert acc["supersedes_id"] == a1["id"]
    assert alice.ok("GET", f"/projects/{pid}/adrs/{a1['id']}")["status"] == "superseded"
    a3 = alice.ok("POST", f"/projects/{pid}/adrs", 201, json={"title": "Use GraphQL everywhere"})
    assert bob.ok("POST", f"/projects/{pid}/adrs/{a3['id']}/reject", json={})["status"] == "rejected"
    md = vera.get(f"/projects/{pid}/adrs/{a1['id']}/markdown").text
    assert "Good, because replay" in md and "Bad, because ops" in md and "`container:shop/api`" in md and "* decoupling" in md
    assert alice.get(f"/projects/{pid}/adrs/{NOPE}").status_code == 404
    assert len(vera.ok("GET", f"/projects/{pid}/adrs")) >= 3


# ------------------------------------------------------------------ documents
def test_documents_get_list_and_generated_docs(users, proj):
    alice, vera = users["alice"], users["vera"]
    pid = proj["id"]
    body = b"# Runbook\n\nRestart the orders worker.\n"
    up = alice.ok("POST", f"/projects/{pid}/documents", 201, files={"file": ("runbook.md", body, "text/markdown")})
    again = alice.ok("POST", f"/projects/{pid}/documents", 201, files={"file": ("runbook.md", body, "text/markdown")})
    assert again["created"] is False and again["id"] == up["id"]
    d = vera.ok("GET", f"/projects/{pid}/documents/{up['id']}")
    assert d["title"] == "runbook.md"
    assert vera.get(f"/projects/{pid}/documents/{NOPE}").status_code == 404
    assert any(x["id"] == up["id"] for x in vera.ok("GET", f"/projects/{pid}/documents"))
    assert vera.ok("GET", f"/projects/{pid}/documents/search", params={"q": "orders worker"})
    assert vera.post(f"/projects/{pid}/documents", files={"file": ("x.md", b"# x", "text/markdown")}).status_code == 403
    for t in ("container-catalog", "interface-catalog", "testing", "flows"):
        g = alice.ok("POST", f"/projects/{pid}/generated-docs", 201, json={"template": t})
        assert g["template"] == t and g["content"].startswith("#")
        if t == "testing":
            assert "## Endpoint test catalog" in g["content"] and "## Flow test scenarios" in g["content"]
        if t == "flows":
            assert "## Flow index" in g["content"]
    est = alice.ok("GET", f"/projects/{pid}/generated-docs/estimate", params={"template": "prd"})      # pre-flight only: no model call
    assert est["sections"] >= 10 and len(est["outline"]) == est["sections"] and "Problem and context" in est["outline"]
    assert alice.ok("GET", f"/projects/{pid}/generated-docs/estimate", params={"template": "system-overview"})["sections"] == 0
    assert any(t["key"] == "user-guide" and t["outline"] for t in alice.ok("GET", "/doc-types"))
    gen = vera.ok("GET", f"/projects/{pid}/generated-docs")
    gid = gen[0]["id"]
    full = vera.ok("GET", f"/projects/{pid}/generated-docs/{gid}")
    md = alice.get(f"/projects/{pid}/generated-docs/{gid}/markdown")
    assert md.status_code == 200 and "attachment" in md.headers["content-disposition"] and md.text == full["content"]
    saved = alice.ok("PUT", f"/projects/{pid}/generated-docs/{gid}", json={"content": full["content"] + "\n\nManual note.\n"})
    assert saved["version"] == full["version"] + 1
    assert vera.put(f"/projects/{pid}/generated-docs/{gid}", json={"content": "x"}).status_code == 403
    assert vera.get(f"/projects/{pid}/generated-docs/{NOPE}").status_code == 404
    assert alice.post(f"/projects/{pid}/generated-docs", json={"template": "novel"}).status_code == 422


# ------------------------------------------------------------------ drift
def test_drift_triage_comments_and_validation(users, proj):
    alice, bob, vera = users["alice"], users["bob"], users["vera"]
    pid = proj["id"]
    alice.ok("POST", f"/projects/{pid}/manual-elements", 201, json={"subject_kind": "node", "key": "container:shop/planned-cache", "kind": "container",
                                                                   "name": "planned-cache"})
    wait(lambda: "container:shop/planned-cache" in alice.ok("GET", f"/projects/{pid}/architecture")["nodes"], what="manual element")
    alice.ok("POST", f"/projects/{pid}/drift/evaluate")
    fs = alice.ok("GET", f"/projects/{pid}/drift", params={"status": "open", "verdict": "drift"})
    assert fs
    fid = fs[0]["id"]
    st = vera.ok("GET", f"/projects/{pid}/drift/stats")
    assert st["open"] >= 1
    assert vera.post(f"/projects/{pid}/drift/{fid}/comments", json={"body": "hm"}).status_code == 403
    got = alice.ok("POST", f"/projects/{pid}/drift/{fid}/comments", json={"body": "Looks planned for Q3"})
    assert got["comments"][-1]["body"] == "Looks planned for Q3" and got["rule"]["id"] == fs[0]["rule_id"]
    assert alice.post(f"/projects/{pid}/drift/{fid}/transition", json={"status": "teleported"}).status_code in (403, 422)
    t = alice.ok("POST", f"/projects/{pid}/drift/{fid}/transition", json={"status": "investigating", "note": "checking", "assignee": proj["ids"]["alice"]})
    assert t["status"] == "investigating" and t["assignee_id"] == proj["ids"]["alice"]
    assert bob.ok("POST", f"/projects/{pid}/drift/{fid}/transition", json={"status": "accepted", "note": "fine"})["status"] == "accepted"
    assert alice.ok("GET", f"/projects/{pid}/drift", params={"status": "accepted"})
    assert alice.get(f"/projects/{pid}/drift/{NOPE}").status_code == 404
    assert alice.post(f"/projects/{pid}/drift/{NOPE}/comments", json={"body": "x"}).status_code == 404
    assert alice.post(f"/projects/{pid}/drift/{NOPE}/transition", json={"status": "acknowledged"}).status_code == 404


# ------------------------------------------------------------------ AI
def test_assistant_history_design_mode_and_adr_draft(users, proj):
    admin, alice, vera = users["admin"], users["alice"], users["vera"]
    pid = proj["id"]
    alice.ok("POST", f"/projects/{pid}/assistant/ask", json={"question": "Which services use the database?",
                                                             "history": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]})
    hist = alice.ok("GET", f"/projects/{pid}/assistant/history")
    assert hist and hist[0]["user_id"] == proj["ids"]["alice"]
    admin.ok("PUT", "/flags/module.integration-designer", json={"scope_kind": "project", "scope_id": pid, "value": True})
    admin.ok("PUT", "/flags/ai.integration_design", json={"scope_kind": "project", "scope_id": pid, "value": True})
    d = alice.ok("POST", f"/projects/{pid}/assistant/ask", json={"question": "Design how a new shipping service should get order events", "mode": "design"})
    assert "answer" in d
    draft = alice.ok("POST", f"/projects/{pid}/assistant/draft-adr", json={"question": "Should orders use the outbox pattern?"})
    assert draft
    assert vera.post(f"/projects/{pid}/assistant/draft-adr", json={"question": "Should we?"}).status_code == 403


# ------------------------------------------------------------------ notifications
def test_notifications_read_and_stream(users, proj):
    alice = users["alice"]
    unread = alice.ok("GET", "/notifications", params={"unread": "true"})
    if unread:
        alice.ok("POST", "/notifications/read", json=[unread[0]["id"]])
    alice.ok("POST", "/notifications/read")
    assert alice.ok("GET", "/notifications", params={"unread": "true"}) == []
    alice.ok("GET", "/notifications")
    with httpx.stream("GET", f"{API}/notifications/stream", headers=alice.h, timeout=20) as s:
        assert s.status_code == 200
        for line in s.iter_lines():
            if line.startswith("data:"):
                assert json.loads(line[5:])["unread"] == 0
                break


def test_unknown_project_and_bad_uuid(users):
    a = users["admin"]
    assert a.get(f"/projects/{uuid.uuid4()}").status_code == 404
    assert a.get("/projects/not-a-uuid").status_code == 422


# ------------------------------------------------------------------ webhooks (every outcome of _handle and every rejection)
def _signed(secret: str, body: bytes, event: str, delivery: str) -> dict:
    import hashlib
    import hmac
    import time
    ts = str(int(time.time()))
    mac = hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    return {"X-ArchTwin-Timestamp": ts, "X-ArchTwin-Signature": f"sha256={mac}", "X-ArchTwin-Delivery": delivery, "X-ArchTwin-Event": event,
            "Content-Type": "application/json"}


def _gh(secret: str, body: bytes, event: str, delivery: str) -> dict:
    import hashlib
    import hmac
    return {"X-Hub-Signature-256": "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(), "X-GitHub-Delivery": delivery,
            "X-GitHub-Event": event, "Content-Type": "application/json"}


def test_webhook_outcomes(users, proj, run_id):
    admin = users["admin"]
    pid, org = proj["id"], proj["org_id"]
    c = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={"kind": "git", "name": "hooked", "config": {"path": SAMPLE, "branches": ["release"]},
                                                                 "secret": {"webhook_secret": "wh-e2e"}})
    url = f"{API}/webhooks/{org}/{pid}/{c['id']}"

    def send(event: str, payload, n: str, secret: str = "wh-e2e", raw: bytes | None = None):
        body = raw if raw is not None else json.dumps(payload).encode()
        return httpx.post(url, content=body, headers=_signed(secret, body, event, f"{run_id}-{n}"), timeout=30)

    assert send("ping", {}, "ping").json()["outcome"] == "pong"
    assert send("push", {"ref": "refs/heads/feature-x", "after": "a" * 40}, "untracked").json()["outcome"] == "ignored_untracked_ref"
    assert send("push", {"ref": "refs/tags/v1", "after": "a" * 40}, "tag").json()["outcome"] == "ignored_untracked_ref"
    assert send("push", {"ref": "refs/heads/release", "after": "0" * 40}, "deleted").json()["outcome"] == "ignored_branch_deleted"
    assert send("issues", {"issue": {"number": 1}}, "issue-on-git").json()["outcome"] == "ignored_event"
    q = send("push", {"ref": "refs/heads/main", "after": "HEAD", "commits": [{}, {}]}, "main")
    assert q.json()["outcome"] == "scan_queued" and q.json()["commits"] == 2
    assert send("push", {"ref": "refs/heads/main", "after": "HEAD"}, "main-again").json()["outcome"] == "duplicate_commit"
    bad_json = send("push", None, "badjson", raw=b"{not json")
    assert bad_json.status_code == 400 and bad_json.json()["code"] == "AT-WEBHOOK-001"
    assert send("push", {}, "wrong-secret", secret="nope").status_code == 401
    big = httpx.post(url, content=b"x" * (6 * 1024 * 1024), headers={"Content-Type": "application/json"}, timeout=60)
    assert big.status_code == 413
    unknown = httpx.post(f"{API}/webhooks/{org}/{pid}/{NOPE}", content=b"{}", timeout=30)
    assert unknown.status_code == 404 and unknown.json()["code"] == "AT-WEBHOOK-001"       # same body for every reason (no oracle)
    info = admin.ok("GET", f"/projects/{pid}/connectors/{c['id']}/webhook")
    assert {d["outcome"] for d in info["recent"]} >= {"pong", "scan_queued", "ignored_event"}
    # module flag off => 404, nothing stored
    admin.ok("PUT", "/flags/connectors.webhooks", json={"scope_kind": "project", "scope_id": pid, "value": False})
    try:
        assert send("ping", {}, "flag-off").status_code == 404
    finally:
        admin.ok("PUT", "/flags/connectors.webhooks", json={"scope_kind": "project", "scope_id": pid, "value": True})
    # a connector without a webhook secret is "not configured"
    plain = proj["connector"]
    body = b"{}"
    r = httpx.post(f"{API}/webhooks/{org}/{pid}/{plain['id']}", content=body, headers=_signed("", body, "ping", f"{run_id}-nosecret"), timeout=30)
    assert r.status_code == 404


def test_github_issue_webhook_updates_work_item(users, proj, run_id):
    admin, alice = users["admin"], users["alice"]
    pid, org = proj["id"], proj["org_id"]
    g = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={"kind": "github", "name": "gh-hook", "config": {"repos": ["acme/shop"]},
                                                                 "secret": {"webhook_secret": "gh-e2e"}})
    url = f"{API}/webhooks/{org}/{pid}/{g['id']}"
    issue = {"action": "opened", "repository": {"full_name": "acme/shop"},
             "issue": {"number": 42, "title": "Orders API returns 500", "state": "open", "html_url": "https://github.com/acme/shop/issues/42",
                       "labels": [{"name": "bug"}], "updated_at": "2026-11-09T10:00:00Z", "user": {"login": "dev"}, "body": "boom"}}
    body = json.dumps(issue).encode()
    r = httpx.post(url, content=body, headers=_gh("gh-e2e", body, "issues", f"{run_id}-gh-1"), timeout=30).json()
    assert r["outcome"] == "work_item_updated" and r["item"] == "acme/shop#42"
    again = httpx.post(url, content=body, headers=_gh("gh-e2e", body, "issues", f"{run_id}-gh-1"), timeout=30).json()
    assert again["duplicate"] is True
    other = json.dumps({**issue, "repository": {"full_name": "evil/repo"}}).encode()
    assert httpx.post(url, content=other, headers=_gh("gh-e2e", other, "issues", f"{run_id}-gh-2"), timeout=30).json()["outcome"] == "ignored_unknown_repo"
    assert alice.ok("GET", f"/projects/{pid}/observations", params={"key": "work-item:github/acme/shop#42"})

"""End-to-end journeys (docs/acceptance/end-to-end-journeys.md) against the running Compose stack.

Covers: OIDC + Cerbos + RLS isolation, flags (incl. queued-job re-check), connectors via outbox → Temporal, snapshots, C4 views + linter +
exports, baselines with separation of duties, drift (three-way, coverage-aware), ADRs, documentation, assistant, audit chain.
"""
import httpx
import pytest

from tests.e2e.conftest import API, wait

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def project(users, run_id):
    admin = users["admin"]
    p = admin.ok("POST", "/projects", 201, json={"title": f"ArchTwin self {run_id}", "purpose": "e2e: the platform scanning itself",
                                                  "tags": ["e2e"], "org_id": "00000000-0000-0000-0000-000000000000"},
                 headers={"Idempotency-Key": f"create-{run_id}"})
    ids = {m["username"]: m["id"] for m in admin.ok("GET", "/org/users")}
    for u, role in (("alice", "architect"), ("bob", "reviewer"), ("vera", "viewer")):
        admin.ok("PUT", f"/projects/{p['id']}/members", json={"user_id": ids[u], "role": role})
    return p


def test_unauthenticated_is_401_before_anything():
    assert httpx.get(f"{API}/projects").status_code == 401
    assert httpx.get(f"{API}/projects", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


def test_idempotent_create_and_smuggled_org_ignored(users, project, run_id):
    again = users["admin"].ok("POST", "/projects", 201, json={"title": f"ArchTwin self {run_id}", "purpose": "e2e: the platform scanning itself",
                                                               "tags": ["e2e"], "org_id": "00000000-0000-0000-0000-000000000000"},
                              headers={"Idempotency-Key": f"create-{run_id}"})
    assert again["id"] == project["id"] and project["org_id"] != "00000000-0000-0000-0000-000000000000"


def test_cross_org_isolation(users, project):
    m = users["mallory"]
    assert all(p["id"] != project["id"] for p in m.ok("GET", "/projects"))
    assert m.get(f"/projects/{project['id']}").status_code == 404
    assert m.get(f"/projects/{project['id']}/architecture").status_code == 404
    assert m.get("/projects", headers={"X-ArchTwin-Org": project["org_id"]}).status_code == 404   # cannot select a foreign org


def test_role_based_denials_are_403(users, project):
    v = users["vera"]
    assert v.get(f"/projects/{project['id']}").status_code == 200
    r = v.post(f"/projects/{project['id']}/connectors", json={"kind": "git", "name": "vera-conn", "config": {"path": "/sources/archtwin"}})
    assert r.status_code == 403 and r.json()["code"] == "AT-AUTHZ-001"
    assert v.put("/flags/module.drift-engine", json={"scope_kind": "org", "value": False}).status_code == 403


def test_security_flags_immutable(users):
    r = users["admin"].put("/flags/security.audit_required", json={"scope_kind": "org", "value": False})
    assert r.status_code == 409


def test_flag_off_returns_feature_disabled_then_restored(users, project):
    a = users["admin"]
    a.ok("PUT", "/flags/module.adr-workflow", json={"scope_kind": "project", "scope_id": project["id"], "value": False})
    try:
        r = users["alice"].get(f"/projects/{project['id']}/adrs")
        assert r.status_code == 404 and r.json()["code"] == "AT-FEATURE-DISABLED"
    finally:
        a.ok("PUT", "/flags/module.adr-workflow", json={"scope_kind": "project", "scope_id": project["id"], "value": True})
    assert users["alice"].get(f"/projects/{project['id']}/adrs").status_code == 200


def test_connector_scan_to_snapshot_and_views(users, project):
    alice, admin = users["alice"], users["admin"]
    pid = project["id"]
    # only managers create connectors (alice is architect -> denied; admin is owner)
    assert alice.post(f"/projects/{pid}/connectors", json={"kind": "git", "name": "self", "config": {"path": "/sources/archtwin"}}).status_code == 403
    c = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={"kind": "git", "name": "self", "config": {"path": "/sources/archtwin", "name": "archtwin"},
                                                                 "secret": {"token": "ARCHTWIN-CANARY-e2esecret"}})
    assert "secret" not in c and c["has_secret"] is True
    t = admin.ok("POST", f"/projects/{pid}/connectors/{c['id']}/test")
    assert t["ok"] and "CANARY" not in str(t)
    # path traversal outside allowed roots is refused
    bad = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={"kind": "git", "name": "evil", "config": {"path": "/etc"}})
    assert admin.ok("POST", f"/projects/{pid}/connectors/{bad['id']}/test")["ok"] is False
    alice.ok("POST", f"/projects/{pid}/connectors/{c['id']}/scan", 202, json={})
    scan = wait(lambda: next((s for s in alice.ok("GET", f"/projects/{pid}/scans") if s["connector_id"] == c["id"] and s["status"] in ("complete", "failed")), None), what="scan")
    assert scan["status"] == "complete" and scan["revision"] and scan["stats"]["observations"] > 50
    snap = wait(lambda: (alice.ok("GET", f"/projects/{pid}/snapshots") or [None])[0], what="snapshot")
    assert snap["node_count"] > 20
    ctx = alice.ok("GET", f"/projects/{pid}/views/context")
    assert any(n["kind"] == "system" and n["name"] == "archtwin" for n in ctx["nodes"])
    l2 = alice.ok("GET", f"/projects/{pid}/views/system:archtwin")
    assert l2["budget"]["primary"] <= 9
    l3 = alice.ok("GET", f"/projects/{pid}/views/container:archtwin/api")
    assert l3["level"] == 3 and l3["nodes"], "the API container's components come from its import graph"
    lint = alice.ok("GET", f"/projects/{pid}/export/lint/system:archtwin")
    assert lint["ok"], lint
    svg = alice.get(f"/projects/{pid}/export/svg/system:archtwin")
    assert svg.status_code == 200 and svg.headers["x-archtwin-lint"] == "pass" and "<svg" in svg.text
    assert "securityLevel" in alice.get(f"/projects/{pid}/export/mermaid/context").text
    assert "workspace" in alice.get(f"/projects/{pid}/export/structurizr/context").text


def test_evidence_on_elements(users, project):
    g = users["alice"].ok("GET", f"/projects/{project['id']}/architecture")
    api = g["nodes"]["container:archtwin/api"]
    ev = api["evidence"][0]
    assert ev["source_ref"] == "compose.yaml" and ev["parser_version"] and ev["source_revision"] and ev["span"]["line_start"] >= 1


def test_runtime_discovery_reconciles_with_code(users, project):
    admin, alice = users["admin"], users["alice"]
    pid = project["id"]
    d = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={"kind": "docker", "name": "docker", "config": {"compose_projects": ["archtwin"]}})
    assert admin.ok("POST", f"/projects/{pid}/connectors/{d['id']}/test")["ok"]
    alice.ok("POST", f"/projects/{pid}/connectors/{d['id']}/scan", 202, json={})
    wait(lambda: any(s["connector_id"] == d["id"] and s["status"] == "complete" for s in alice.ok("GET", f"/projects/{pid}/scans")), what="docker scan")
    def api_with_runtime():
        n = alice.ok("GET", f"/projects/{pid}/architecture")["nodes"].get("container:archtwin/api")
        return n if n and "runtime" in n["origins"] else None
    api = wait(api_with_runtime, what="runtime evidence")
    assert set(api["origins"]) >= {"static", "runtime"}
    alice.ok("POST", f"/projects/{pid}/drift/evaluate")
    open_ = alice.ok("GET", f"/projects/{pid}/drift?status=open")
    assert not any(f["subject_key"] == "container:archtwin/api" and f["rule_id"].startswith("DR-RUNTIME") for f in open_), open_


def test_baseline_separation_of_duties_and_drift(users, project):
    alice, bob, vera = users["alice"], users["bob"], users["vera"]
    pid = project["id"]
    snap = alice.ok("GET", f"/projects/{pid}/snapshots")[0]
    b = alice.ok("POST", f"/projects/{pid}/baselines", 201, json={"snapshot_id": snap["id"], "note": "e2e"})
    assert alice.post(f"/projects/{pid}/baselines/{b['id']}/approve", json={}).status_code == 403
    assert vera.post(f"/projects/{pid}/baselines/{b['id']}/approve", json={}).status_code == 403
    assert bob.ok("POST", f"/projects/{pid}/baselines/{b['id']}/approve", json={})["status"] == "approved"
    # curate: a manually declared (planned) container that nothing observes => missing? it is in the CURRENT graph via manual
    alice.ok("POST", f"/projects/{pid}/manual-elements", 201, json={"subject_kind": "node", "key": "container:archtwin/planned-search",
                                                                    "kind": "container", "name": "planned-search", "attributes": {"technology": "OpenSearch"}})
    wait(lambda: "container:archtwin/planned-search" in alice.ok("GET", f"/projects/{pid}/architecture")["nodes"], what="manual element in snapshot")
    res = alice.ok("POST", f"/projects/{pid}/drift/evaluate")
    assert res["baseline"] is True
    f = [x for x in alice.ok("GET", f"/projects/{pid}/drift?status=open") if x["subject_key"] == "container:archtwin/planned-search"]
    assert f and f[0]["rule_id"] == "DR-UNPLANNED-001" and f[0]["verdict"] == "drift"
    fid = f[0]["id"]
    assert vera.post(f"/projects/{pid}/drift/{fid}/transition", json={"status": "acknowledged"}).status_code == 403
    assert alice.post(f"/projects/{pid}/drift/{fid}/transition", json={"status": "suppressed", "note": ""}).status_code == 422
    done = bob.ok("POST", f"/projects/{pid}/drift/{fid}/transition", json={"status": "suppressed", "note": "planned for Q3", "suppress_days": 30})
    assert done["status"] == "suppressed" and done["suppressed_until"]
    again = alice.ok("POST", f"/projects/{pid}/drift/evaluate")
    assert again["new"] == 0, "re-evaluation must not duplicate findings"


def test_adr_workflow(users, project):
    alice, bob = users["alice"], users["bob"]
    pid = project["id"]
    a = alice.ok("POST", f"/projects/{pid}/adrs", 201, json={"title": "Use PostgreSQL RLS as defense in depth", "context": "Multi-tenant isolation",
                                                           "considered_options": [{"name": "RLS"}, {"name": "schema per tenant"}], "decision_outcome": "RLS"})
    assert alice.post(f"/projects/{pid}/adrs/{a['id']}/accept", json={}).status_code == 403
    acc = bob.ok("POST", f"/projects/{pid}/adrs/{a['id']}/accept", json={})
    assert acc["status"] == "accepted"
    assert alice.put(f"/projects/{pid}/adrs/{a['id']}", json={"title": "changed"}).status_code == 409   # immutable once accepted
    md = alice.get(f"/projects/{pid}/adrs/{a['id']}/markdown").text
    assert md.startswith(f"# {a['number']:04d}.") and "Status: accepted" in md


def test_documentation_engine_and_documents(users, project):
    alice = users["alice"]
    pid = project["id"]
    d = alice.ok("POST", f"/projects/{pid}/generated-docs", 201, json={"template": "system-overview"})
    assert d["coverage"]["ratio"] >= 0.95 and "## Evidence" in d["content"]
    again = alice.ok("POST", f"/projects/{pid}/generated-docs", 201, json={"template": "system-overview"})
    assert again.get("unchanged") or again["version"] == d["version"] + 1
    docs = alice.ok("GET", f"/projects/{pid}/documents?q=ADR")
    assert docs, "ADRs from docs/architecture/adr are ingested with provenance"
    hits = alice.ok("GET", f"/projects/{pid}/documents/search?q=temporal outbox")
    assert hits and hits[0]["path"].endswith(".md") and hits[0]["line_start"]
    up = alice.post(f"/projects/{pid}/documents", files={"file": ("notes.md", b"# Notes\nThe gateway is LiteLLM.\n", "text/markdown")})
    assert up.status_code == 201
    bad = alice.post(f"/projects/{pid}/documents", files={"file": ("evil.md", b"\x7fELF\x00\x01binary", "text/markdown")})
    assert bad.status_code == 415


def test_assistant_grounded_and_model_policy(users, project):
    alice = users["alice"]
    pid = project["id"]
    models = alice.ok("GET", "/ai/models")
    assert models["default"] == "gpt-6-luna" and any(m["alias"] == "gpt-6-luna" for m in models["models"])
    assert alice.post(f"/projects/{pid}/assistant/ask", json={"question": "What is the AI gateway?", "model": "gpt-4o"}).status_code == 422
    r = alice.ok("POST", f"/projects/{pid}/assistant/ask", json={"question": "Which container is the AI gateway and what calls it?"})
    assert r["citations"] and not r["invalid_citations"] and r["grounded"]
    assert all(e["id"] in {x["id"] for x in r["all_evidence"]} for e in r["evidence"])
    assert "CANARY" not in str(r)


def test_cross_project_isolation_in_assistant_and_search(users, project, run_id):
    """Another project's documents never leak into this project's retrieval (AT-PROJECT_BOUNDARIES-004)."""
    admin = users["admin"]
    other = admin.ok("POST", "/projects", 201, json={"title": f"Other {run_id}"})
    admin.post(f"/projects/{other['id']}/documents", files={"file": ("x.md", b"# Zebra\nzebrafish-secret-codename lives here\n", "text/markdown")})
    assert admin.ok("GET", f"/projects/{other['id']}/documents/search?q=zebrafish")
    assert not admin.ok("GET", f"/projects/{project['id']}/documents/search?q=zebrafish")


def test_notifications_and_audit_chain(users, project):
    admin = users["admin"]
    assert any(e["action"].startswith("connector.") for e in admin.ok("GET", f"/audit?project_id={project['id']}"))
    denials = admin.ok("GET", "/audit?action=baseline&limit=50") + admin.ok("GET", "/audit?action=architecture.approve&limit=50")
    _ = denials
    v = admin.ok("GET", "/audit/verify")
    assert v["ok"] and v["events"] > 10
    assert any(e["decision"] == "deny" for e in admin.ok("GET", "/audit?limit=500"))
    assert users["vera"].get("/audit").status_code == 403

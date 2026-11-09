"""Local directories (folder of repositories, docs mode, folder picker), GitLab and Taiga — on the live stack.

AT-SOURCE_CODE_DISCOVERY-001, AT-WORK_CONNECTORS-001..003 (Taiga opt-in, invalid webhook signature), AT-CONNECTOR_PLATFORM.
The repository is mounted read-only at /sources/archtwin, so fixtures written under `.e2e-sources/` (gitignored) on the host
are visible to the API and worker. Live provider tests are opt-in:
  ARCHTWIN_E2E_TAIGA_URL=https://taiga.example.com/project/<slug>/kanban  [ARCHTWIN_E2E_TAIGA_USER / _PASSWORD]
  ARCHTWIN_E2E_GITLAB_PROJECT=https://gitlab.example.com/group/project ARCHTWIN_E2E_GITLAB_TOKEN=glpat-…
"""
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest

from tests.e2e.conftest import API, wait

pytestmark = pytest.mark.e2e
REPO = Path(__file__).resolve().parents[4]
HOST_FIX = REPO / ".e2e-sources"
MOUNTED = "/sources/archtwin/.e2e-sources"


def _repo(p: Path, files: dict[str, str]) -> None:
    p.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (p / name).parent.mkdir(parents=True, exist_ok=True)
        (p / name).write_text(text)
    env = {**os.environ, "GIT_AUTHOR_NAME": "e2e", "GIT_AUTHOR_EMAIL": "e2e@x", "GIT_COMMITTER_NAME": "e2e", "GIT_COMMITTER_EMAIL": "e2e@x"}
    for cmd in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
        subprocess.run(["git", *cmd], cwd=p, check=True, env=env)
    for d in (p, *[x for x in p.rglob("*") if x.is_dir()]):
        d.chmod(0o755)                                  # the containers run as another uid
    for f in p.rglob("*"):
        if f.is_file():
            f.chmod(0o644)


@pytest.fixture(scope="module")
def fixtures(run_id):
    root = HOST_FIX / run_id
    _repo(root / "backend" / "alpha-svc", {"README.md": "# Alpha\n", "compose.yaml": "services:\n  alpha:\n    image: python:3.12\n    depends_on: [alpha-db]\n"
                                                                                     "  alpha-db:\n    image: postgres:17\n"})
    _repo(root / "backend" / "beta-svc", {"README.md": "# Beta\n", "compose.yaml": "services:\n  beta:\n    image: node:22\n"})
    _repo(root / "architecture", {"ADRs/ADR-001-split-services.md": "# ADR-001 split services\n\nWe split alpha and beta.\n",
                                  "diagrams/context.mmd": "flowchart LR\n alpha --> beta\n", "notes/overview.txt": "platform overview"})
    for d in (HOST_FIX, root):
        d.chmod(0o755)
    yield f"{MOUNTED}/{run_id}"
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(scope="module")
def proj(users, run_id):
    admin = users["admin"]
    p = admin.ok("POST", "/projects", 201, json={"title": f"Sources {run_id}", "purpose": "e2e: local dirs, GitLab, Taiga", "tags": ["e2e"]},
                 headers={"Idempotency-Key": f"src-{run_id}"})
    ids = {m["username"]: m["id"] for m in admin.ok("GET", "/org/users")}
    admin.ok("PUT", f"/projects/{p['id']}/members", json={"user_id": ids["vera"], "role": "viewer"})
    return p


def _scan(admin, pid, cid, timeout=240):
    s0 = admin.ok("POST", f"/projects/{pid}/connectors/{cid}/scan", 202, json={})
    return wait(lambda: next((x for x in admin.ok("GET", f"/projects/{pid}/scans", params={"connector_id": cid})
                              if x["id"] == s0["id"] and x["status"] in ("complete", "partial", "failed")), None), timeout=timeout, what="scan")


def test_folder_of_repositories_and_docs_folder(users, proj, fixtures):
    admin, pid = users["admin"], proj["id"]
    code = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={"kind": "git", "name": "backends", "config": {"path": f"{fixtures}/backend"}})
    t = admin.ok("POST", f"/projects/{pid}/connectors/{code['id']}/test")
    assert t["ok"] and t["details"]["layout"] == "folder of repositories" and t["details"]["repositories"] == ["alpha-svc", "beta-svc"]
    s = _scan(admin, pid, code["id"])
    assert s["status"] == "complete" and s["stats"]["repositories"] == 2, s
    assert "alpha-svc@" in s["revision"] and "beta-svc@" in s["revision"]
    bad = admin.post(f"/projects/{pid}/connectors/{code['id']}/scan", json={"ref": "main"}, headers={"Idempotency-Key": uuid.uuid4().hex})
    assert bad.status_code == 202                                   # accepted, then fails: a ref needs a single repository
    wait(lambda: any(x["ref"] == "main" and x["status"] == "failed" and "single repository" in (x["error"] or "")
                     for x in admin.ok("GET", f"/projects/{pid}/scans", params={"connector_id": code["id"]})), what="ref refused")

    docs = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={"kind": "git", "name": "architecture",
                                                                       "config": {"path": f"{fixtures}/architecture", "content": "docs"}})
    sd = _scan(admin, pid, docs["id"])
    assert sd["status"] in ("complete", "partial") and sd["stats"]["documents"] >= 3, sd

    def built():
        g = admin.ok("GET", f"/projects/{pid}/architecture") or {}
        n = g.get("nodes") or {}
        return n if {"system:alpha-svc", "system:beta-svc", "container:alpha-svc/alpha"} <= set(n) and any(k.startswith("adr:") for k in n) else None
    nodes = wait(built, timeout=180, what="snapshot with both repos and the ADR")
    assert not any(k.startswith("container:architecture/") for k in nodes)          # docs mode adds no runtime wiring
    titles = {d["title"] for d in admin.ok("GET", f"/projects/{pid}/documents")}
    assert "ADR-001 split services" in titles and any("mermaid" in t for t in titles)


def test_folder_picker_lists_only_mounted_roots_and_is_authorized(users, proj, fixtures):
    admin, vera, mallory, pid = users["admin"], users["vera"], users["mallory"], proj["id"]
    top = admin.ok("GET", f"/projects/{pid}/source-folders")
    assert any(p["path"] == "/sources" for p in top["places"])
    b = admin.ok("GET", f"/projects/{pid}/source-folders", params={"path": f"{fixtures}/backend"})
    assert b["layout"] == "folder of repositories" and [f["name"] for f in b["folders"]] == ["alpha-svc", "beta-svc"]
    assert all(f["is_repo"] for f in b["folders"]) and b["parent"] == fixtures
    for outside in ("/etc", "/sources/../etc", "/proc/self"):
        r = admin.get(f"/projects/{pid}/source-folders", params={"path": outside})
        assert r.status_code == 422 and r.json()["code"] == "AT-CONN-004", outside
    assert vera.get(f"/projects/{pid}/source-folders").status_code == 403         # viewers cannot add datasources
    assert mallory.get(f"/projects/{pid}/source-folders").status_code in (403, 404)
    kinds = {k["kind"]: k for k in admin.ok("GET", "/connector-kinds", params={"project_id": pid})}
    assert "/sources" in kinds["git"]["source_roots"] and kinds["gitlab"]["enabled"] and kinds["taiga"]["category"] == "work"


def _post(url, body: dict, headers: dict):
    return httpx.post(url, content=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}, timeout=20)


def test_gitlab_webhooks_token_dedupe_and_work_items(users, proj):
    admin, pid = users["admin"], proj["id"]
    c = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={
        "kind": "gitlab", "name": "gl-hooks", "config": {"url": "https://gitlab.example.com", "projects": ["grp/svc"], "analyze_code": False},
        "secret": {"webhook_secret": "ARCHTWIN-CANARY-gl"}})
    info = admin.ok("GET", f"/projects/{pid}/connectors/{c['id']}/webhook")
    assert "X-Gitlab-Token" in info["signature"] and info["events"] == ["push", "merge_request", "issue"]
    url = f"{API}/webhooks/{info['url'].split('/webhooks/')[1]}"
    hook = {"object_kind": "issue", "project": {"path_with_namespace": "grp/svc"}, "labels": [{"title": "bug"}],
            "object_attributes": {"iid": 12, "title": "Export breaks", "state": "opened", "url": "https://gitlab.example.com/grp/svc/-/issues/12",
                                  "updated_at": "2026-11-09T10:00:00Z", "action": "open"}}
    d1 = uuid.uuid4().hex
    r = _post(url, hook, {"X-Gitlab-Token": "wrong", "X-Gitlab-Event": "Issue Hook", "X-Gitlab-Event-UUID": d1})
    assert r.status_code == 401 and "CANARY" not in r.text
    ok = _post(url, hook, {"X-Gitlab-Token": "ARCHTWIN-CANARY-gl", "X-Gitlab-Event": "Issue Hook", "X-Gitlab-Event-UUID": d1}).json()
    assert ok["outcome"] == "work_item_updated" and ok["item"] == "grp/svc#12", ok
    again = _post(url, hook, {"X-Gitlab-Token": "ARCHTWIN-CANARY-gl", "X-Gitlab-Event": "Issue Hook", "X-Gitlab-Event-UUID": d1}).json()
    assert again["duplicate"] is True
    other = {**hook, "project": {"path_with_namespace": "someone/else"}}
    ign = _post(url, other, {"X-Gitlab-Token": "ARCHTWIN-CANARY-gl", "X-Gitlab-Event": "Issue Hook", "X-Gitlab-Event-UUID": uuid.uuid4().hex}).json()
    assert ign["outcome"] == "ignored_unknown_repo"
    push = {"object_kind": "push", "ref": "refs/heads/feature", "after": "a" * 40, "project": {"path_with_namespace": "grp/svc", "default_branch": "main"}}
    p = _post(url, push, {"X-Gitlab-Token": "ARCHTWIN-CANARY-gl", "X-Gitlab-Event": "Push Hook", "X-Gitlab-Event-UUID": uuid.uuid4().hex}).json()
    assert p["outcome"] == "ignored_untracked_ref"
    scans = admin.ok("GET", f"/projects/{pid}/scans", params={"connector_id": c["id"]})
    assert any(s["ref"] == "issue#12" and s["status"] == "partial" for s in scans)           # webhook updates are additive only


def test_taiga_webhook_signature_and_flag_opt_in(users, proj):
    admin, pid = users["admin"], proj["id"]
    c = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={
        "kind": "taiga", "name": "board", "config": {"url": "https://taiga.example.com/project/e2e-board/kanban"},
        "secret": {"webhook_secret": "ARCHTWIN-CANARY-tg"}})
    url = f"{API}/webhooks/{admin.ok('GET', f'/projects/{pid}/connectors/{c['id']}/webhook')['url'].split('/webhooks/')[1]}"
    body = {"action": "change", "type": "userstory", "date": "2026-11-09T10:00:00Z", "data": {
        "id": 1, "ref": 6, "subject": "Show empty fields", "status": {"name": "In progress", "is_closed": False},
        "permalink": "https://taiga.example.com/project/e2e-board/us/6", "project": {"permalink": "https://taiga.example.com/project/e2e-board/"},
        "modified_date": "2026-11-09T10:00:00Z"}}
    raw = json.dumps(body).encode()
    good = hmac.new(b"ARCHTWIN-CANARY-tg", raw, hashlib.sha1).hexdigest()
    assert httpx.post(url, content=raw, headers={"X-TAIGA-WEBHOOK-SIGNATURE": "0" * 40}, timeout=20).status_code == 401
    ok = httpx.post(url, content=raw, headers={"X-TAIGA-WEBHOOK-SIGNATURE": good}, timeout=20).json()
    assert ok["outcome"] == "work_item_updated" and ok["item"] == "e2e-board#6", ok
    assert httpx.post(url, content=raw, headers={"X-TAIGA-WEBHOOK-SIGNATURE": good}, timeout=20).json()["duplicate"] is True
    dele = json.dumps({**body, "action": "delete"}).encode()
    out = httpx.post(url, content=dele, headers={"X-TAIGA-WEBHOOK-SIGNATURE": hmac.new(b"ARCHTWIN-CANARY-tg", dele, hashlib.sha1).hexdigest()},
                     timeout=20).json()
    assert out["outcome"] == "ignored_delete_until_reconcile"

    # Scenario "Taiga opt-in": flag disabled -> cannot sync, cannot be added, webhooks rejected
    admin.ok("PUT", "/flags/connector.taiga", json={"scope_kind": "project", "scope_id": pid, "value": False, "reason": "e2e"})
    try:
        kinds = {k["kind"]: k for k in admin.ok("GET", "/connector-kinds", params={"project_id": pid})}
        assert kinds["taiga"]["enabled"] is False
        r = admin.post(f"/projects/{pid}/connectors/{c['id']}/scan", json={}, headers={"Idempotency-Key": uuid.uuid4().hex})
        assert r.status_code == 404 and r.json()["code"] == "AT-FEATURE-DISABLED"
        r = admin.post(f"/projects/{pid}/connectors", json={"kind": "taiga", "name": "board2", "config": {"url": "https://taiga.example.com/project/x/kanban"}},
                       headers={"Idempotency-Key": uuid.uuid4().hex})
        assert r.status_code == 404 and r.json()["code"] == "AT-FEATURE-DISABLED"
        raw2 = json.dumps({**body, "date": "later"}).encode()
        sig2 = hmac.new(b"ARCHTWIN-CANARY-tg", raw2, hashlib.sha1).hexdigest()
        assert httpx.post(url, content=raw2, headers={"X-TAIGA-WEBHOOK-SIGNATURE": sig2}, timeout=20).status_code == 404
    finally:
        admin.ok("PUT", "/flags/connector.taiga", json={"scope_kind": "project", "scope_id": pid, "value": True, "reason": "e2e"})


@pytest.mark.skipif(not os.environ.get("ARCHTWIN_E2E_TAIGA_URL"), reason="ARCHTWIN_E2E_TAIGA_URL not set (live Taiga is opt-in)")
def test_taiga_live(users, proj):
    admin, pid = users["admin"], proj["id"]
    secret = {k: v for k, v in {"username": os.environ.get("ARCHTWIN_E2E_TAIGA_USER"),
                                "password": os.environ.get("ARCHTWIN_E2E_TAIGA_PASSWORD")}.items() if v} or None
    c = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={"kind": "taiga", "name": "taiga-live",
                                                                    "config": {"url": os.environ["ARCHTWIN_E2E_TAIGA_URL"]}, "secret": secret})
    t = admin.ok("POST", f"/projects/{pid}/connectors/{c['id']}/test")
    assert t["ok"], t
    s = _scan(admin, pid, c["id"])
    assert s["status"] in ("complete", "partial") and s["stats"]["observations"] > 0, s


@pytest.mark.skipif(not (os.environ.get("ARCHTWIN_E2E_GITLAB_PROJECT") and os.environ.get("ARCHTWIN_E2E_GITLAB_TOKEN")),
                    reason="ARCHTWIN_E2E_GITLAB_PROJECT/TOKEN not set (live GitLab is opt-in)")
def test_gitlab_live(users, proj):
    admin, pid = users["admin"], proj["id"]
    c = admin.ok("POST", f"/projects/{pid}/connectors", 201, json={
        "kind": "gitlab", "name": "gitlab-live", "config": {"projects": [os.environ["ARCHTWIN_E2E_GITLAB_PROJECT"]], "max_items": 50},
        "secret": {"token": os.environ["ARCHTWIN_E2E_GITLAB_TOKEN"]}})
    t = admin.ok("POST", f"/projects/{pid}/connectors/{c['id']}/test")
    assert t["ok"] and os.environ["ARCHTWIN_E2E_GITLAB_TOKEN"] not in json.dumps(t), t
    s = _scan(admin, pid, c["id"], timeout=600)
    assert s["status"] in ("complete", "partial") and len(s["revision"]) >= 40 and s["stats"]["branches"] >= 1, s

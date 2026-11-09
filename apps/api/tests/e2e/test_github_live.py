"""GitHub connector against a real public repository (unauthenticated, read-only). Skipped offline or when rate limited."""
import os

import httpx
import pytest

from tests.e2e.conftest import wait

REPO = os.environ.get("ARCHTWIN_E2E_GITHUB_REPO", "bogdancstrike/ArchTwin")
CODE_REF = os.environ.get("ARCHTWIN_E2E_GITHUB_REF", "feat/walking-skeleton-m1")      # branch that carries the code


def _github_ok() -> bool:
    try:
        r = httpx.get("https://api.github.com/rate_limit", timeout=5)
        return r.status_code == 200 and r.json()["resources"]["core"]["remaining"] >= 10
    except (httpx.HTTPError, KeyError, ValueError):
        return False


pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True, scope="module")
def _require_target():          # probed lazily (not at import) so unit-test collection never touches the network
    if not _github_ok():
        pytest.skip("GitHub API unreachable or rate limited")


def test_github_public_repo_scan(users, run_id):
    admin = users["admin"]
    p = admin.ok("POST", "/projects", 201, json={"title": f"GitHub live {run_id}", "purpose": "e2e: GitHub connector", "tags": ["e2e"]},
                 headers={"Idempotency-Key": f"gh-{run_id}"})
    c = admin.ok("POST", f"/projects/{p['id']}/connectors", 201, json={
        "kind": "github", "name": "gh", "config": {"repos": [REPO], "max_items": 50, "system_names": {REPO: "archtwin"}}})
    t = admin.ok("POST", f"/projects/{p['id']}/connectors/{c['id']}/test")
    assert t["ok"] and t["details"]["repos"][REPO]["default_branch"]
    admin.ok("POST", f"/projects/{p['id']}/connectors/{c['id']}/scan", 202, json={})
    s = wait(lambda: next((x for x in admin.ok("GET", f"/projects/{p['id']}/scans") if x["status"] in ("complete", "partial", "failed")), None),
             timeout=300, what="github scan")
    assert s["status"] == "complete", s
    assert len(s["revision"]) == 40 and s["stats"]["branches"] >= 1 and "issues" in s["stats"] and "pull_requests" in s["stats"]
    # any ref can be scanned (compare two commits): the code branch yields the containers
    admin.ok("POST", f"/projects/{p['id']}/connectors/{c['id']}/scan", 202, json={"ref": CODE_REF})
    s2 = wait(lambda: next((x for x in admin.ok("GET", f"/projects/{p['id']}/scans") if x["ref"] == CODE_REF
                            and x["status"] in ("complete", "partial", "failed")), None), timeout=300, what="github ref scan")
    assert s2["status"] == "complete" and s2["stats"]["services"] > 5, s2
    def built():
        g = admin.ok("GET", f"/projects/{p['id']}/architecture") or {}
        return g["nodes"] if "container:archtwin/api" in (g.get("nodes") or {}) else None
    nodes = wait(built, timeout=120, what="snapshot with code")
    assert nodes["system:archtwin"]["attributes"].get("github") == REPO or "static" in nodes["system:archtwin"]["origins"]

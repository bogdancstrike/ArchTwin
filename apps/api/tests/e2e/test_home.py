"""Personal home (/home): cross-project overview never leaks projects the caller cannot view."""
import pytest

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def project(users, run_id):
    return users["admin"].ok("POST", "/projects", 201, json={"title": f"Home check {run_id}", "purpose": "e2e: home", "tags": ["e2e"]},
                             headers={"Idempotency-Key": f"home-{run_id}"})


def test_home_lists_only_visible_projects(users, project):
    admin = users["admin"].ok("GET", "/home")
    ids = {p["id"] for p in admin["projects"]}
    assert project["id"] in ids
    assert admin["totals"]["projects"] == len(admin["projects"])
    p = next(x for x in admin["projects"] if x["id"] == project["id"])
    assert {"snapshot", "drift", "adrs", "freshness", "last_activity"} <= set(p)
    assert all(a["project_id"] in ids for a in admin["attention"] + admin["activity"])


def test_home_outsider_sees_nothing(users, project):
    out = users["mallory"].ok("GET", "/home")
    assert out["projects"] == [] and out["attention"] == [] and out["activity"] == []
    assert out["totals"]["projects"] == 0


def test_home_requires_auth():
    import httpx

    from tests.e2e.conftest import API
    assert httpx.get(f"{API}/home", timeout=10).status_code == 401


def test_project_home_cards(users, project):
    h = users["admin"].ok("GET", f"/projects/{project['id']}/home")
    assert {"freshness", "architecture", "drift", "decisions", "assistant"} <= set(h)
    assert "observations_by_origin" in h["freshness"] and "recent_scans" in h["freshness"]

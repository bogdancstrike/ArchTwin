"""Exports of Architecture, Flows, Drift, Decisions and Docs as Markdown, DOCX, PDF and ZIP — on the live stack."""
import io
import json
import zipfile

import pytest

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def proj(users, run_id):
    admin = users["admin"]
    p = admin.ok("POST", "/projects", 201, json={"title": f"Export {run_id}", "purpose": "e2e: exports", "tags": ["e2e"]},
                 headers={"Idempotency-Key": f"export-{run_id}"})
    ids = {m["username"]: m["id"] for m in admin.ok("GET", "/org/users")}
    admin.ok("PUT", f"/projects/{p['id']}/members", json={"user_id": ids["vera"], "role": "viewer"})
    admin.ok("POST", f"/projects/{p['id']}/adrs", 201, json={"title": "Use PostgreSQL for orders", "context": "Orders need transactions.",
                                                               "decision_outcome": "PostgreSQL 17 → one schema per service",
                                                               "considered_options": [{"name": "PostgreSQL", "pros": ["ACID"], "cons": []}]})
    return p


def _get(client, path, **params):
    r = client.get(path, params=params)
    assert r.status_code == 200, f"{path} {params} -> {r.status_code} {r.text[:300]}"
    return r


@pytest.mark.parametrize("resource", ["decisions", "architecture"])
def test_every_format_downloads(users, proj, resource):
    admin, pid = users["admin"], proj["id"]
    md = _get(admin, f"/projects/{pid}/export/{resource}", format="md")
    assert md.headers["content-type"].startswith("text/markdown") and "attachment" in md.headers["content-disposition"]
    assert proj["slug"] in md.headers["content-disposition"] and f"-{resource}-" in md.headers["content-disposition"]
    assert md.text.startswith("# ") and "Exported from ArchTwin" in md.text
    if resource == "decisions":
        assert "Use PostgreSQL for orders" in md.text and "PostgreSQL 17 → one schema" in md.text
    docx = _get(admin, f"/projects/{pid}/export/{resource}", format="docx")
    assert docx.content[:2] == b"PK" and "wordprocessingml" in docx.headers["content-type"]
    pdf = _get(admin, f"/projects/{pid}/export/{resource}", format="pdf")
    assert pdf.content.startswith(b"%PDF")
    z = zipfile.ZipFile(io.BytesIO(_get(admin, f"/projects/{pid}/export/{resource}", format="zip").content))
    man = json.loads(z.read("manifest.json"))
    assert man["resource"] == resource and man["project"]["id"] == pid
    assert {n.rsplit(".", 1)[-1] for n in z.namelist()} >= {"json", "md", "docx", "pdf"}


def test_single_items_filters_permissions_and_audit(users, proj):
    admin, vera, mallory, pid = users["admin"], users["vera"], users["mallory"], proj["id"]
    adr = admin.ok("GET", f"/projects/{pid}/adrs")[0]
    one = _get(admin, f"/projects/{pid}/export/decisions", format="md", id=adr["id"])
    assert one.text.startswith(f"# {adr['number']:04d}. Use PostgreSQL for orders")
    assert admin.get(f"/projects/{pid}/export/decisions", params={"format": "md", "id": "00000000-0000-0000-0000-000000000000"}).status_code == 404
    assert _get(admin, f"/projects/{pid}/export/drift", format="md", status="open").text.count("Filters: status=open") == 1
    assert _get(admin, f"/projects/{pid}/export/flows", format="md").text.startswith("# ")
    assert _get(vera, f"/projects/{pid}/export/architecture", format="md").status_code == 200          # viewers export what they see
    assert mallory.get(f"/projects/{pid}/export/architecture", params={"format": "md"}).status_code in (403, 404)
    assert admin.get(f"/projects/{pid}/export/secrets", params={"format": "md"}).status_code == 422
    assert admin.get(f"/projects/{pid}/export/decisions", params={"format": "exe"}).status_code == 422
    events = admin.ok("GET", "/audit/search", params={"q": "export.decisions", "project_id": pid})
    assert any("export.decisions" in json.dumps(e) for e in events["items"])

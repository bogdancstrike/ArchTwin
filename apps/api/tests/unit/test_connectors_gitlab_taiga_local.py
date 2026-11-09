"""GitLab + Taiga adapters (HTTP mocked), their webhook verification, the local folder-of-repositories / docs mode, egress TLS.

AT-SOURCE_CODE_DISCOVERY-001 (GitLab, local directories), AT-WORK_CONNECTORS-001..003 (GitLab issues/MRs, Taiga),
phase-02 tasks 3.1, 6.1, 6.2, 6.3.
"""
import hashlib
import hmac
import inspect
import ipaddress
import json
import subprocess
from pathlib import Path

import httpx
import pytest
import respx

from archtwin.common import egress
from archtwin.connectors import registry, webhooks
from archtwin.connectors.adapters import git_repo
from archtwin.connectors.adapters.git_repo import GitRepoConnector, discover_repos
from archtwin.connectors.adapters.gitlab import GitLabConnector, split_project
from archtwin.connectors.adapters.taiga import TaigaConnector, parse_target
from archtwin.connectors.sdk import ScanResult


class _S:
    def __init__(self, **kw):
        self.private_host_allowlist, self.insecure_tls_hosts, self.source_roots, self.docling_url = set(), set(), [], ""
        self.__dict__.update(kw)


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda host: [ipaddress.ip_address("140.82.112.5")])
    monkeypatch.setattr(egress, "settings", lambda: _S())


# ------------------------------------------------------------------ registry / flags
def test_registry_gates_new_kinds_behind_module_and_provider_flags():
    assert registry.MODULE_FLAG["gitlab"] == "module.source-code-discovery" and registry.get("gitlab").flag == "connector.gitlab"
    assert registry.MODULE_FLAG["taiga"] == "module.work-connectors" and registry.get("taiga").flag == "connector.taiga"
    assert registry.CATEGORY["taiga"] == "work"
    kinds = {m["kind"]: m for m in registry.manifests()}
    assert {"gitlab", "taiga"} <= set(kinds) and "token" in kinds["gitlab"]["secret"] and "password" in kinds["taiga"]["secret"]


# ------------------------------------------------------------------ GitLab
GL = "https://gitlab.example.com"
API = f"{GL}/api/v4"
P = "grp/sub/service-data"
PE = "grp%2Fsub%2Fservice-data"


def test_split_project_accepts_urls_and_paths():
    assert split_project(f"{GL}/grp/sub/service-data", None) == (GL, P)
    assert split_project(f"{GL}/grp/sub/service-data.git", None) == (GL, P)
    assert split_project(f"{GL}/grp/sub/service-data/-/tree/main", None) == (GL, P)
    assert split_project("grp/sub/service-data", GL) == (GL, P)
    with pytest.raises(ValueError):
        split_project("grp/x", None)


async def test_gitlab_rejects_bad_paths_and_mixed_hosts():
    assert not (await GitLabConnector().test({"projects": ["../../etc/passwd"], "url": GL}, {})).ok
    assert not (await GitLabConnector().test({"projects": [], "url": GL}, {})).ok
    t = await GitLabConnector().test({"url": GL, "projects": ["https://other.example.com/a/b"]}, {})
    assert not t.ok and "all projects must be on" in t.warnings[0]


async def test_gitlab_private_host_denied_without_allowlist(monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda host: [ipaddress.ip_address("10.30.11.12")])
    t = await GitLabConnector().test({"projects": [f"{GL}/{P}"]}, {"token": "glpat-x"})
    assert not t.ok and "blocked address range" in t.warnings[0]


@respx.mock
async def test_gitlab_test_warns_on_write_scopes_and_developer_access():
    respx.get(f"{API}/user").mock(return_value=httpx.Response(200, json={"username": "bot"}))
    respx.get(f"{API}/personal_access_tokens/self").mock(return_value=httpx.Response(200, json={"scopes": ["api", "read_repository"]}))
    respx.get(f"{API}/projects/{PE}").mock(return_value=httpx.Response(200, json={
        "id": 5, "visibility": "private", "default_branch": "develop", "web_url": f"{GL}/{P}",
        "permissions": {"project_access": {"access_level": 30}, "group_access": None}}))
    t = await GitLabConnector().test({"projects": [f"{GL}/{P}"]}, {"token": "glpat-secret"})
    assert t.ok and t.details["projects"][P]["default_branch"] == "develop"
    assert any("write/admin scopes ['api']" in w for w in t.warnings) and any("can push" in w for w in t.warnings)
    assert "glpat-secret" not in json.dumps(t.details) + str(t.warnings)
    assert respx.calls[0].request.headers["PRIVATE-TOKEN"] == "glpat-secret"


@respx.mock
async def test_gitlab_test_rejected_token():
    respx.get(f"{API}/user").mock(return_value=httpx.Response(401))
    t = await GitLabConnector().test({"projects": [P], "url": GL}, {"token": "bad"})
    assert not t.ok and "401" in t.warnings[0]


def _mock_gitlab_project(pid=5, path=P, issues=None, mrs=None):
    pe = path.replace("/", "%2F")
    respx.get(f"{API}/projects/{pe}").mock(return_value=httpx.Response(200, json={
        "id": pid, "default_branch": "main", "http_url_to_repo": f"{GL}/{path}.git", "web_url": f"{GL}/{path}", "visibility": "private"}))
    respx.get(url__startswith=f"{API}/projects/{pid}/repository/commits/").mock(return_value=httpx.Response(200, json={"id": "c" * 40}))
    respx.get(url__startswith=f"{API}/projects/{pid}/repository/branches").mock(return_value=httpx.Response(200, json=[
        {"name": "main", "commit": {"id": "c" * 40, "committed_date": "2026-11-01"}, "protected": True}, {"name": "feat", "commit": {"id": "d" * 40}}]))
    respx.get(url__startswith=f"{API}/projects/{pid}/issues").mock(return_value=httpx.Response(200, json=issues or []))
    respx.get(url__startswith=f"{API}/projects/{pid}/merge_requests").mock(return_value=httpx.Response(200, json=mrs or []))


@respx.mock
async def test_gitlab_scan_work_items_closing_keywords_and_coverage():
    _mock_gitlab_project(issues=[{"iid": 7, "title": "Export fails", "state": "opened", "labels": ["bug"], "web_url": "u7",
                                  "author": {"username": "ana"}, "assignees": [{"username": "dan"}]}],
                         mrs=[{"iid": 3, "title": "Fix export", "description": "Closes #7, see #9", "state": "merged", "web_url": "m3",
                               "source_branch": "fix", "target_branch": "main", "sha": "e" * 40, "merged_at": "2026-11-02"}])
    r = await GitLabConnector().scan({"projects": [f"{GL}/{P}"], "analyze_code": False}, {"token": "t"}, None)
    keys = {o.subject_key: o for o in r.observations}
    issue, mr = keys[f"work-item:gitlab/{P}#7"], keys[f"work-item:gitlab/{P}!3"]
    assert issue.origin == "issue" and issue.attributes["state"] == "open" and issue.attributes["labels"] == ["bug"]
    assert issue.attributes["assignees"] == ["dan"] and issue.attributes["author"] == "ana"
    assert mr.attributes["type"] == "merge_request" and mr.attributes["base"] == "main" and mr.attributes["head"]["sha"] == "e" * 40
    assert f"work-item:gitlab/{P}!3|implements|work-item:gitlab/{P}#7" in keys
    assert not any(k.endswith("#9") for k in keys)                       # "see #9" is not a closing keyword
    assert keys["system:service-data"].attributes["gitlab"] == P
    assert r.revision == "c" * 40 and r.complete and r.stats["issues"] == 1 and r.stats["merge_requests"] == 1
    assert f"work-item:gitlab/{P}#" in r.coverage["prefixes"]


@respx.mock
async def test_gitlab_groups_expand_and_webhook_ref_scans_one_project_partially():
    respx.get(url__startswith=f"{API}/groups/grp%2Fsub/projects").mock(return_value=httpx.Response(200, json=[
        {"path_with_namespace": P}, {"path_with_namespace": "grp/sub/service-iam"}]))
    _mock_gitlab_project(5, P)
    _mock_gitlab_project(6, "grp/sub/service-iam")
    full = await GitLabConnector().scan({"url": GL, "groups": ["grp/sub"], "analyze_code": False}, {}, None)
    assert full.complete and full.stats["projects"] == 2 and "system:service-iam" in {o.subject_key for o in full.observations}
    one = await GitLabConnector().scan({"url": GL, "groups": ["grp/sub"], "analyze_code": False}, {}, f"{P}@{'c' * 40}")
    assert one.stats["projects"] == 1 and not one.complete                 # other projects unseen: additive, never tombstones
    with pytest.raises(ValueError):
        await GitLabConnector().scan({"url": GL, "projects": [P], "analyze_code": False}, {}, "other/proj@abc")


@respx.mock
async def test_gitlab_clones_with_oauth2_user(monkeypatch):
    _mock_gitlab_project()
    seen = {}

    async def fake_scan(self, cfg, secret, ref):
        seen.update(cfg=cfg, secret=secret, ref=ref)
        return ScanResult(revision="f" * 40)
    monkeypatch.setattr(GitRepoConnector, "scan", fake_scan)
    await GitLabConnector().scan({"projects": [f"{GL}/{P}"], "issues": False, "merge_requests": False, "content": "docs"}, {"token": "t"}, "feat")
    assert seen["cfg"]["url"] == f"{GL}/{P}.git" and seen["secret"] == {"token": "t", "username": "oauth2"} and seen["ref"] == "feat"
    assert seen["cfg"]["content"] == "docs"
    assert GitRepoConnector._auth_url("https://h/x.git", {"token": "t", "username": "oauth2"}) == "https://oauth2:t@h/x.git"
    with pytest.raises(ValueError):
        GitRepoConnector._auth_url("https://h/x.git", {"token": "t", "username": "a@b:c"})


def test_gitlab_and_taiga_have_no_write_calls():
    import archtwin.connectors.adapters.gitlab as gl
    import archtwin.connectors.adapters.taiga as tg
    for mod in (gl, tg):
        src = inspect.getsource(mod)
        for verb in (".post(", ".put(", ".patch(", ".delete(", 'method="POST"'):
            assert verb not in src, (mod.__name__, verb)
    assert inspect.getsource(tg).count("guarded_login(") == 1             # Taiga's only non-GET call is the login exchange


# ------------------------------------------------------------------ Taiga
TG = "https://taiga.example.com"
TAPI = f"{TG}/api/v1"


def test_taiga_parse_target_from_ui_url():
    assert parse_target({"url": f"{TG}/project/qsint-1/kanban"}) == (TG, TAPI, "qsint-1")
    assert parse_target({"url": TG, "project": "Team-X"}) == (TG, TAPI, "team-x")
    for bad in ({"url": TG}, {"url": "ftp://h/project/x"}, {"url": f"{TG}/project/../x"}, {}):
        with pytest.raises(ValueError):
            parse_target(bad)


def _mock_taiga(paginated_stories=True):
    respx.get(f"{TAPI}/projects/by_slug").mock(return_value=httpx.Response(200, json={
        "id": 50, "name": "QSINT", "slug": "qsint-1", "modified_date": "2026-09-17T12:12:04Z", "my_permissions": ["view_us"]}))
    p1 = [{"id": 101, "ref": 6, "subject": "Show empty fields", "is_closed": False, "status_extra_info": {"name": "New", "is_closed": False},
           "tags": [["prod", "#000"]], "assigned_to_extra_info": {"username": "dan"}, "milestone_slug": "s1", "milestone_name": "Sprint 1",
           "epics": [{"id": 9, "ref": 1, "subject": "Release"}], "modified_date": "2026-09-22T06:16:37Z", "total_points": 3}]
    p2 = [{"id": 102, "ref": 8, "subject": "Done story", "is_closed": True, "status_extra_info": {"name": "Done", "is_closed": True},
           "finish_date": "2026-10-01", "modified_date": "2026-10-01T00:00:00Z"}]
    hdr = {"x-paginated": "true", "x-pagination-count": "2"}

    def stories(request):
        page = request.url.params.get("page")
        if page == "1":       # Taiga advertises a plain-http next link; the adapter must not follow it
            return httpx.Response(200, json=p1, headers={**hdr, "x-pagination-next": "http://taiga.example.com/api/v1/userstories?page=2"})
        return httpx.Response(200, json=p2, headers=hdr)
    respx.get(url__startswith=f"{TAPI}/userstories").mock(side_effect=stories)
    respx.get(url__startswith=f"{TAPI}/tasks").mock(return_value=httpx.Response(200, json=[
        {"id": 201, "ref": 15, "subject": "Filter by user", "status_extra_info": {"name": "New", "is_closed": False},
         "user_story_extra_info": {"id": 101, "ref": 6}, "modified_date": "2026-09-18T09:55:16Z"}]))
    respx.get(url__startswith=f"{TAPI}/epics").mock(return_value=httpx.Response(200, json=[
        {"id": 9, "ref": 1, "subject": "Release-V2", "status_extra_info": {"name": "New", "is_closed": False}}]))
    respx.get(url__startswith=f"{TAPI}/issues").mock(return_value=httpx.Response(200, json=[]))
    respx.get(url__startswith=f"{TAPI}/milestones").mock(return_value=httpx.Response(200, json=[
        {"id": 3, "slug": "s1", "name": "1", "closed": False, "estimated_start": "2026-09-01", "estimated_finish": "2026-09-15"}]))


@respx.mock
async def test_taiga_scan_maps_items_links_and_pages_by_number():
    _mock_taiga()
    r = await TaigaConnector().scan({"url": f"{TG}/project/qsint-1/kanban", "system": "qsint"}, {}, None)
    keys = {o.subject_key: o for o in r.observations}
    us = keys["work-item:taiga/qsint-1#6"]
    assert us.origin == "issue" and us.attributes["type"] == "user_story" and us.attributes["status"] == "New"
    assert us.attributes["labels"] == ["prod"] and us.attributes["assignees"] == ["dan"] and us.attributes["sprint"] == "Sprint 1"
    assert us.attributes["url"] == f"{TG}/project/qsint-1/us/6"
    assert keys["work-item:taiga/qsint-1#8"].attributes["state"] == "closed"            # page 2 fetched via ?page=2 (https)
    assert "work-item:taiga/qsint-1#15|implements|work-item:taiga/qsint-1#6" in keys       # task -> story
    assert "work-item:taiga/qsint-1#6|implements|work-item:taiga/qsint-1#1" in keys        # story -> epic
    assert "work-item:taiga/qsint-1#6|references|work-item:taiga/qsint-1/sprint/s1" in keys
    assert "work-item:taiga/qsint-1#6|references|system:qsint" in keys
    assert r.complete and r.stats["userstories"] == 2 and r.stats["tasks"] == 1 and r.stats["sprints"] == 1
    assert all(str(c.request.url).startswith("https://") for c in respx.calls)
    assert r.revision == "taiga:qsint-1@2026-10-01T00:00:00Z"


@respx.mock
async def test_taiga_password_login_and_failure():
    login = respx.post(f"{TAPI}/auth").mock(return_value=httpx.Response(200, json={"auth_token": "sess-1"}))
    _mock_taiga()
    t = await TaigaConnector().test({"url": f"{TG}/project/qsint-1/kanban"}, {"username": "u", "password": "pw-secret"})
    assert t.ok and t.details["authenticated"] and login.called
    assert json.loads(login.calls[0].request.content) == {"type": "normal", "username": "u", "password": "pw-secret"}
    assert respx.get(f"{TAPI}/projects/by_slug").calls[-1].request.headers["Authorization"] == "Bearer sess-1"
    assert "pw-secret" not in json.dumps(t.details) + str(t.warnings)
    login.mock(return_value=httpx.Response(401, json={}))
    bad = await TaigaConnector().test({"url": f"{TG}/project/qsint-1/kanban"}, {"username": "u", "password": "wrong"})
    assert not bad.ok and "login failed" in bad.warnings[0]


@respx.mock
async def test_taiga_warns_on_write_permissions_and_anonymous():
    respx.get(f"{TAPI}/projects/by_slug").mock(return_value=httpx.Response(200, json={
        "id": 50, "slug": "qsint-1", "my_permissions": ["view_us", "add_us", "modify_task"]}))
    t = await TaigaConnector().test({"url": f"{TG}/project/qsint-1/kanban"}, {})
    assert t.ok and any("no credentials" in w for w in t.warnings) and any("write permissions" in w for w in t.warnings)


@respx.mock
async def test_taiga_max_items_makes_scan_partial():
    _mock_taiga()
    r = await TaigaConnector().scan({"url": f"{TG}/project/qsint-1/kanban", "max_items": 1}, {}, None)
    assert not r.complete and any("max_items" in w for w in r.warnings)


def test_taiga_webhook_shape_is_normalized():
    r = ScanResult()
    TaigaConnector.work_item(r, TG, "qsint-1", {"ref": 15, "subject": "x", "status": {"name": "Closed", "is_closed": True},
                                                "assigned_to": {"username": "ana"}, "milestone": {"slug": "s2", "name": "S2"},
                                                "user_story": {"ref": 6}, "tags": ["a"], "permalink": f"{TG}/project/qsint-1/task/15"}, "task")
    keys = {o.subject_key: o for o in r.observations}
    t = keys["work-item:taiga/qsint-1#15"]
    assert t.attributes["state"] == "closed" and t.attributes["assignees"] == ["ana"] and t.attributes["sprint"] == "S2"
    assert "work-item:taiga/qsint-1#15|implements|work-item:taiga/qsint-1#6" in keys


# ------------------------------------------------------------------ webhook signatures (AT-WORK_CONNECTORS-001 invalid signature)
def test_gitlab_webhook_token():
    h = {"x-gitlab-token": "s3", "x-gitlab-event-uuid": "u-1"}
    assert webhooks.verify("gitlab", "s3", h, b"{}") == "u-1"
    assert webhooks.verify("gitlab", "s3", {"x-gitlab-token": "s3", "idempotency-key": "k-2"}, b"{}") == "k-2"
    for bad in ({"x-gitlab-token": "nope", "x-gitlab-event-uuid": "u"}, {"x-gitlab-event-uuid": "u"}):
        with pytest.raises(webhooks.Rejected) as e:
            webhooks.verify("gitlab", "s3", bad, b"{}")
        assert e.value.status == 401
    with pytest.raises(webhooks.Rejected):
        webhooks.verify("gitlab", "s3", {"x-gitlab-token": "s3"}, b"{}")       # no delivery id


def test_taiga_webhook_signature():
    body = b'{"type":"userstory","action":"change"}'
    good = hmac.new(b"k", body, hashlib.sha1).hexdigest()
    did = webhooks.verify("taiga", "k", {"x-taiga-webhook-signature": good}, body)
    assert did.startswith("taiga-") and did == webhooks.verify("taiga", "k", {"x-taiga-webhook-signature": good}, body)   # stable -> dedupe
    for h, b in (({"x-taiga-webhook-signature": good}, body + b" "), ({"x-taiga-webhook-signature": "0" * 40}, body), ({}, body)):
        with pytest.raises(webhooks.Rejected):
            webhooks.verify("taiga", "k", h, b)


def test_webhook_event_names():
    assert webhooks._event("gitlab", {"x-gitlab-event": "Merge Request Hook"}, {}) == "merge_request"
    assert webhooks._event("gitlab", {"x-gitlab-event": "Push Hook"}, {}) == "push"
    assert webhooks._event("taiga", {}, {"type": "task"}) == "taiga.task"
    assert webhooks._event("taiga", {}, {"type": "test"}) == "ping"


# ------------------------------------------------------------------ local directories: folder of repos, docs mode
def _repo(p: Path, files: dict[str, str]) -> None:
    p.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (p / name).parent.mkdir(parents=True, exist_ok=True)
        (p / name).write_text(text)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"}
    for cmd in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
        subprocess.run(["git", *cmd], cwd=p, check=True, env=env)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(git_repo, "settings", lambda: _S(source_roots=[str(tmp_path)]))
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    backend = tmp_path / "backend"
    _repo(backend / "service-data", {"README.md": "# Service data\n", "compose.yaml": "services:\n  api:\n    image: python:3.12\n",
                                     "docs/ADRs/ADR-001_db.md": "# ADR-001 database\n", "src/deep/notes.md": "# deep notes\n"})
    _repo(backend / "service-iam", {"README.md": "# IAM\n", "compose.yaml": "services:\n  iam:\n    image: keycloak/keycloak\n"})
    (backend / "node_modules" / "x").mkdir(parents=True)
    _repo(backend / "node_modules" / "x" / "dep", {"a.md": "x"})                # skipped dirs are never searched
    (backend / "service-iam" / "uncommitted.md").write_text("# not committed\n")
    return tmp_path


def test_discover_repos_filters(workspace):
    b = workspace / "backend"
    assert discover_repos(b) == ["service-data", "service-iam"]
    assert discover_repos(b, include=["service-d*"]) == ["service-data"]
    assert discover_repos(b, exclude=["*iam"]) == ["service-data"]
    assert discover_repos(workspace) == ["backend/service-data", "backend/service-iam"]


async def test_folder_of_repos_scans_each_repo_as_a_system(workspace):
    cfg = {"path": str(workspace / "backend")}
    t = await GitRepoConnector().test(cfg, {})
    assert t.ok and t.details["layout"] == "folder of repositories" and t.details["repositories"] == ["service-data", "service-iam"]
    r = await GitRepoConnector().scan(cfg, {}, None)
    keys = {o.subject_key for o in r.observations}
    assert {"system:service-data", "system:service-iam", "container:service-data/api", "container:service-iam/iam"} <= keys
    assert r.complete and r.stats["repositories"] == 2
    assert r.revision.startswith("service-data@") and ",service-iam@" in r.revision
    paths = {d.path for d in r.documents}
    assert "service-data/README.md" in paths and "service-data/docs/ADRs/ADR-001_db.md" in paths
    assert "service-iam/uncommitted.md" not in paths                           # HEAD only: the working tree is not read
    assert "system:service-data" in r.coverage["prefixes"] and "system:service-iam" in r.coverage["prefixes"]
    with pytest.raises(ValueError, match="single repository"):
        await GitRepoConnector().scan(cfg, {}, "main")


async def test_single_repo_child_keeps_refs(workspace):
    r = await GitRepoConnector().scan({"path": str(workspace / "backend" / "service-data")}, {}, "main")
    assert len(r.revision) == 40 and "system:service-data" in {o.subject_key for o in r.observations}


async def test_docs_mode_ingests_every_document_and_diagram_without_runtime_wiring(workspace):
    arch = workspace / "architecture"
    arch.mkdir()
    (arch / "manual.docx").write_bytes(b"PK\x03\x04")
    _repo(arch, {"ADRs/ADR-002-cache.md": "# ADR-002 cache\n", "notes/summary.txt": "plain text notes",
                 "diagrams/context.mmd": "flowchart LR\n a-->b\n", "compose.yaml": "services:\n  x:\n    image: redis\n",
                 "spec/api.yaml": "openapi: 3.0.0\ninfo: {title: Data API, version: '1'}\npaths: {/items: {get: {}}}\n"})
    r = await GitRepoConnector().scan({"path": str(arch), "content": "docs"}, {}, None)
    docs = {d.path: d for d in r.documents}
    assert {"ADRs/ADR-002-cache.md", "notes/summary.txt", "diagrams/context.mmd"} <= set(docs)
    assert "```mermaid" in docs["diagrams/context.mmd"].text and "diagram" in docs["diagrams/context.mmd"].tags
    keys = {o.subject_key for o in r.observations}
    assert "adr:architecture/ADRs/ADR-002-cache.md" in keys and any(k.startswith("contract:") for k in keys)
    assert not any(k.startswith("container:") for k in keys)                  # docs mode: no runtime wiring from compose
    assert r.stats["binary_documents"] == 1 and any("PDF/DOCX" in w for w in r.warnings)     # no docling: counted, not parsed
    auto = await GitRepoConnector().scan({"path": str(arch)}, {}, None)
    assert "notes/summary.txt" not in {d.path for d in auto.documents} and "ADRs/ADR-002-cache.md" in {d.path for d in auto.documents}
    assert not (await GitRepoConnector().test({"path": str(arch), "content": "everything"}, {})).ok


async def test_local_path_outside_roots_and_plain_directory(workspace, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    t = await GitRepoConnector().test({"path": str(outside)}, {})
    assert not t.ok and "allowed source root" in t.warnings[0]
    plain = workspace / "plain"
    (plain / "docs").mkdir(parents=True)
    (plain / "docs" / "x.md").write_text("# X\n")
    t2 = await GitRepoConnector().test({"path": str(plain)}, {})
    assert t2.ok and t2.details["layout"] == "plain directory"
    r = await GitRepoConnector().scan({"path": str(plain)}, {}, None)
    assert r.revision == "working-tree" and "docs/x.md" in {d.path for d in r.documents}


# ------------------------------------------------------------------ egress: TLS verification is an operator decision
def test_tls_verify_only_skipped_for_operator_listed_hosts(monkeypatch):
    monkeypatch.setattr(egress, "settings", lambda: _S(insecure_tls_hosts={"taiga.internal"}))
    assert egress.tls_verify("https://gitlab.example.com/api") is True
    assert egress.tls_verify("https://taiga.internal/api/v1") is False
    assert egress.tls_verify("https://TAIGA.internal./x") is False


@respx.mock
async def test_guarded_login_refuses_redirects_and_private_hosts(monkeypatch):
    respx.post(f"{TAPI}/auth").mock(return_value=httpx.Response(302, headers={"location": "https://evil.example.com/steal"}))
    with pytest.raises(Exception, match="not re-sent to a redirect"):
        await egress.guarded_login(f"{TAPI}/auth", json={"u": 1})
    monkeypatch.setattr(egress, "resolve", lambda host: [ipaddress.ip_address("169.254.169.254")])
    with pytest.raises(Exception, match="blocked address range"):
        await egress.guarded_login(f"{TAPI}/auth", json={"u": 1})


# ------------------------------------------------------------------ folder picker (browse the mounted roots, names only)
def test_browse_lists_roots_folders_and_layouts(workspace):
    top = git_repo.browse(None)
    assert top["path"] == "" and top["folders"][0]["path"] == str(workspace.resolve())
    b = git_repo.browse(str(workspace / "backend"))
    assert b["layout"] == "folder of repositories" and b["repositories"] == 2 and b["parent"] == str(workspace.resolve())
    assert [f["name"] for f in b["folders"]] == ["service-data", "service-iam"]           # node_modules and dot-dirs hidden
    assert all(f["is_repo"] for f in b["folders"])
    sd = git_repo.browse(str(workspace / "backend" / "service-data"))
    assert sd["layout"] == "repository" and "compose" in sd["markers"] and "docs" in sd["markers"]
    assert git_repo.browse(str(workspace))["parent"] == ""                               # at a root: "up" goes to the places list


def test_browse_refuses_paths_outside_roots_and_symlink_escapes(workspace, tmp_path_factory):
    outside = tmp_path_factory.mktemp("secret-place")
    with pytest.raises(ValueError, match="allowed source root"):
        git_repo.browse(str(outside))
    (workspace / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="allowed source root"):
        git_repo.browse(str(workspace / "link"))                                         # resolved before the root check
    assert "link" not in [f["name"] for f in git_repo.browse(str(workspace))["folders"]]
    with pytest.raises(ValueError, match="allowed source root"):
        git_repo.browse(str(workspace / ".." / outside.name))


def test_compose_reset_and_override_tags_are_understood(tmp_path):
    from archtwin.connectors.analyzers.repo import analyze_repository
    (tmp_path / "compose.yaml").write_text("services:\n  api:\n    image: python:3.12\n")
    (tmp_path / "docker-compose.scale.yml").write_text(
        "services:\n  api:\n    ports: !reset []\n    environment: !override\n      A: b\n  worker:\n    image: python:3.12\n")
    r = analyze_repository(tmp_path, "rev", "svc")
    assert not any("invalid YAML" in w for w in r.warnings)
    assert "container:svc/worker" in {o.subject_key for o in r.observations}

"""Fail-closed guards (Cerbos, egress redirects) and connector adapters exercised without live services (HTTP mocked)."""
import ipaddress
import socket
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import Column, MetaData, Table, Text

from archtwin.common import authz, egress
from archtwin.common.db import Principal
from archtwin.common.errors import Problem
from archtwin.connectors.adapters import git_repo, kafka_cluster
from archtwin.connectors.adapters.git_repo import GitRepoConnector
from archtwin.connectors.adapters.http_openapi import HttpOpenApiConnector

PUBLIC = [ipaddress.ip_address("140.82.112.5")]


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda host: PUBLIC)


def principal() -> Principal:
    return Principal(user_id=uuid.uuid4(), subject="s", username="u", display_name="U", org_id=uuid.uuid4(), org_role="member")


# ------------------------------------------------------------------ Cerbos: fail closed
@pytest.fixture
def cerbos(monkeypatch):
    monkeypatch.setattr(authz, "_client", httpx.AsyncClient(base_url="http://cerbos.test", timeout=1))
    with respx.mock(base_url="http://cerbos.test", assert_all_called=False) as m:
        yield m


async def test_check_allows_only_explicit_allow(cerbos):
    cerbos.post("/api/check/resources").respond(json={"results": [{"actions": {"view": "EFFECT_ALLOW", "edit": "EFFECT_DENY"}}]})
    res = await authz.check(principal(), "project", "p1", {"org_id": uuid.uuid4(), "flag": True, "n": None}, ["view", "edit", "delete"])
    assert res == {"view": True, "edit": False, "delete": False}


@pytest.mark.parametrize("resp", [httpx.Response(500), httpx.Response(200, json={"oops": 1})])
async def test_pdp_errors_are_503_never_allow(cerbos, resp):
    cerbos.post("/api/check/resources").mock(return_value=resp)
    with pytest.raises(Problem) as e:
        await authz.allowed(principal(), "project", "view", "p1")
    assert e.value.status_code == 503 and e.value.code == "AT-AUTHZ-002" and e.value.retryable


async def test_pdp_unreachable_is_503(cerbos):
    cerbos.post("/api/check/resources").mock(side_effect=httpx.ConnectError("down"))
    cerbos.post("/api/plan/resources").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(Problem):
        await authz.allowed(principal(), "project", "view")
    with pytest.raises(Problem):
        await authz.plan(principal(), "project", "view")


async def test_plan_untranslatable_condition_denies(cerbos):
    t = Table("t", MetaData(), Column("id", Text), Column("org_id", Text))
    cerbos.post("/api/plan/resources").respond(json={
        "requestId": "x", "actions": ["view"], "resourceKind": "project",
        "filter": {"kind": "KIND_CONDITIONAL", "condition": {"expression": {"operator": "frobnicate", "operands": [
            {"variable": "request.resource.attr.mystery"}, {"value": "1"}]}}}})
    where = await authz.plan_filter(principal(), "project", "view", t, {"request.resource.attr.org_id": t.c.org_id})
    assert str(where.compile(compile_kwargs={"literal_binds": True})) in ("false", "0 = 1")


async def test_plan_always_allowed_has_no_filter(cerbos):
    t = Table("t2", MetaData(), Column("id", Text))
    cerbos.post("/api/plan/resources").respond(json={"requestId": "x", "action": "view", "resourceKind": "project",
                                                     "filter": {"kind": "KIND_ALWAYS_ALLOWED"}})
    where = await authz.plan_filter(principal(), "project", "view", t, {})
    assert str(where.compile(compile_kwargs={"literal_binds": True})) in ("true", "1 = 1")


async def test_health(cerbos):
    cerbos.get("/_cerbos/health").respond(200)
    assert await authz.healthy() is True
    cerbos.get("/_cerbos/health").mock(side_effect=httpx.ConnectError("x"))
    assert await authz.healthy() is False


# ------------------------------------------------------------------ egress: resolution, redirects and size caps
def test_unresolvable_host_denied(monkeypatch):
    def boom(*a, **k):
        raise socket.gaierror("nope")
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    with pytest.raises(egress.EgressDenied, match="cannot resolve"):
        egress.check_url("https://no-such-host.invalid/", allow_hosts=set())


def test_ipv4_mapped_ipv6_private_and_missing_host_denied():
    with pytest.raises(egress.EgressDenied):
        egress.check_url("https://x.test/", allow_hosts=set(), resolver=lambda h: [ipaddress.ip_address("::ffff:10.0.0.1")])
    with pytest.raises(egress.EgressDenied, match="missing host"):
        egress.check_url("https:///path", allow_hosts=set())


@respx.mock
async def test_redirect_to_private_address_is_denied(monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda host: [ipaddress.ip_address("10.0.0.5")] if host == "internal.test" else PUBLIC)
    respx.get("https://public.test/a").respond(302, headers={"location": "https://internal.test/secret"})
    with pytest.raises(Problem) as e:
        await egress.guarded_get("https://public.test/a", allow_hosts=set())
    assert e.value.code == "AT-EGRESS-001"


@respx.mock
async def test_redirect_loop_and_size_cap(public_dns):
    respx.get("https://public.test/loop").respond(302, headers={"location": "/loop"})
    with pytest.raises(Problem) as e:
        await egress.guarded_get("https://public.test/loop", allow_hosts=set())
    assert e.value.code == "AT-EGRESS-003"
    respx.get("https://public.test/big").respond(200, content=b"x" * 2000)
    with pytest.raises(Problem) as e:
        await egress.guarded_get("https://public.test/big", allow_hosts=set(), max_bytes=1000)
    assert e.value.code == "AT-EGRESS-002"
    respx.get("https://public.test/hop").respond(301, headers={"location": "https://public.test/ok"})
    respx.get("https://public.test/ok").respond(200, text="fine")
    assert (await egress.guarded_get("https://public.test/hop", allow_hosts=set())).text == "fine"


# ------------------------------------------------------------------ live OpenAPI adapter
SPEC = """openapi: 3.0.0
info: {title: Orders, version: "2.1"}
paths:
  /orders:
    get: {summary: List orders}
    post: {summary: Create}
    parameters: []
  /orders/{id}:
    delete: null
"""


@respx.mock
async def test_openapi_test_and_scan(public_dns):
    route = respx.get("https://orders.test/openapi.yaml").respond(200, text=SPEC)
    c = HttpOpenApiConnector()
    cfg = {"url": "https://orders.test/openapi.yaml", "system": "shop", "service": "orders"}
    t = await c.test(cfg, {"token": "tkn"})
    assert t.ok and t.details == {"title": "Orders", "paths": 2}
    assert route.calls.last.request.headers["authorization"] == "Bearer tkn"
    r = await c.scan(cfg, {}, None)
    eps = sorted(o.name for o in r.observations if o.kind == "api-endpoint")
    assert eps == ["DELETE /orders/{id}", "GET /orders", "POST /orders"]
    assert any(o.subject_key == "contract:shop/orders/live" and o.attributes["version"] == "2.1" for o in r.observations)
    assert r.coverage["prefixes"] == ["endpoint:shop/orders/"] and r.stats["endpoints"] == 3 and len(r.revision) == 16
    assert "authorization" not in route.calls.last.request.headers


@respx.mock
async def test_openapi_test_reports_failures(public_dns):
    respx.get("https://orders.test/missing").respond(404)
    t = await HttpOpenApiConnector().test({"url": "https://orders.test/missing"}, {})
    assert not t.ok and t.warnings
    t2 = await HttpOpenApiConnector().test({"url": "http://169.254.169.254/latest"}, {})
    assert not t2.ok and t2.warnings


# ------------------------------------------------------------------ Kafka configuration helpers (no broker needed)
def test_kafka_brokers_and_client_conf():
    assert kafka_cluster._brokers({"bootstrap_servers": "PLAINTEXT://k1:9093, SASL_SSL://k2, k3:19092, kafka"}) == [("k1", 9093), ("k2", 9092), ("k3", 19092), ("kafka", 9092)]
    with pytest.raises(ValueError):
        kafka_cluster._brokers({"bootstrap_servers": " , "})
    conf = kafka_cluster._client_conf({"bootstrap_servers": "k1:9092", "security_protocol": "SASL_SSL", "sasl_mechanism": "SCRAM-SHA-512"},
                                      {"sasl_username": "ro", "sasl_password": "pw"})
    assert conf["security.protocol"] == "SASL_SSL" and conf["sasl.mechanism"] == "SCRAM-SHA-512" and conf["sasl.username"] == "ro"
    assert "sasl.username" not in kafka_cluster._client_conf({"bootstrap_servers": "k1"}, {})


async def test_kafka_rejects_bad_config_and_private_brokers(monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda host: [ipaddress.ip_address("10.1.2.3")])
    monkeypatch.setattr(egress, "settings", lambda: type("S", (), {"private_host_allowlist": set()})())
    k = kafka_cluster.KafkaClusterConnector()
    assert (await k.test({}, {})).ok is False
    bad = await k.test({"bootstrap_servers": "broker.internal:9092"}, {})
    assert not bad.ok and "blocked" in bad.warnings[0]
    with pytest.raises(egress.EgressDenied):
        await k.scan({"bootstrap_servers": "broker.internal:9092"}, {}, None)


# ------------------------------------------------------------------ git adapter: path policy, refs, auth URL, non-git trees
@pytest.fixture
def roots(tmp_path, monkeypatch):
    monkeypatch.setattr(git_repo, "settings", lambda: type("S", (), {"source_roots": [str(tmp_path)]})())
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    return tmp_path


def test_git_local_path_policy(roots):
    (roots / "repo").mkdir()
    assert git_repo._local_path({"path": str(roots / "repo")}) == (roots / "repo").resolve()
    with pytest.raises(ValueError, match="allowed source root"):
        git_repo._local_path({"path": "/etc"})
    with pytest.raises(ValueError, match="allowed source root"):
        git_repo._local_path({"path": str(roots / "repo" / ".." / ".." / "etc")})
    with pytest.raises(ValueError, match="not a directory"):
        git_repo._local_path({"path": str(roots / "missing")})


def test_git_auth_url_only_for_https():
    assert GitRepoConnector._auth_url("https://github.com/a/b.git", {"token": "t"}) == "https://x-access-token:t@github.com/a/b.git"
    assert GitRepoConnector._auth_url("http://h/a.git", {"token": "t"}) == "http://h/a.git"
    assert GitRepoConnector._auth_url("https://h/a.git", {}) == "https://h/a.git"


async def test_git_scan_plain_directory_and_bad_refs(roots):
    src = roots / "plain"
    src.mkdir()
    (src / "compose.yaml").write_text("services:\n  api:\n    image: nginx:1.27\n")
    c = GitRepoConnector()
    t = await c.test({"path": str(src)}, {})
    assert t.ok and t.warnings and "not a git repository" in t.warnings[0]
    r = await c.scan({"path": str(src), "name": "plain"}, {}, None)
    assert r.revision == "working-tree" and any(o.subject_key == "container:plain/api" for o in r.observations)
    with pytest.raises(ValueError, match="not found"):
        await c.scan({"path": str(src)}, {}, "v9.9.9")
    with pytest.raises(ValueError, match="invalid ref"):
        await c.scan({"path": str(src)}, {}, "main; rm -rf /")
    assert not (await c.test({"path": "/etc"}, {})).ok


async def test_git_scan_specific_commit_of_local_repo(roots):
    repo = roots / "r"
    repo.mkdir()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
           "HOME": str(roots), "PATH": "/usr/bin:/bin"}

    def git(*a):
        return subprocess.run(["git", *a], cwd=repo, env=env, check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q", "-b", "main")
    (repo / "compose.yaml").write_text("services:\n  one:\n    image: redis:7\n")
    git("add", ".")
    git("commit", "-qm", "one")
    first = git("rev-parse", "HEAD")
    (repo / "compose.yaml").write_text("services:\n  one:\n    image: redis:7\n  two:\n    image: redis:7\n")
    git("commit", "-qam", "two")
    c = GitRepoConnector()
    head = await c.scan({"path": str(repo), "name": "r"}, {}, None)
    old = await c.scan({"path": str(repo), "name": "r"}, {}, first)

    def containers(res):
        return {o.subject_key for o in res.observations if o.kind == "container"}
    assert "container:r/two" in containers(head) and "container:r/two" not in containers(old)
    assert old.revision == first and old.stats["ref"] == first
    assert (await c.test({"path": str(repo)}, {})).details["head"] == head.revision


async def test_git_remote_url_is_egress_checked(monkeypatch):
    monkeypatch.setattr(egress, "settings", lambda: type("S", (), {"private_host_allowlist": set()})())
    t = await GitRepoConnector().test({"url": "https://127.0.0.1/x.git"}, {})
    assert not t.ok
    with pytest.raises(egress.EgressDenied):
        await GitRepoConnector().scan({"url": "file:///etc"}, {}, None)


def test_safe_extract_rejects_traversal(tmp_path: Path):
    import io
    import tarfile
    tp = tmp_path / "evil.tar"
    with tarfile.open(tp, "w") as tf:
        data = b"pwned"
        info = tarfile.TarInfo("../escape.txt")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    (tmp_path / "out").mkdir()
    with pytest.raises(tarfile.TarError):
        git_repo._safe_extract(tp, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()

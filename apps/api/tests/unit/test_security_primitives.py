"""AT-IDENTITY_POLICY-004 (secrets), SSRF egress suite, audit hash chain (AT-AUDIT_PROVENANCE-003), log redaction."""
import base64
import ipaddress
import uuid

import pytest
from cryptography.exceptions import InvalidTag

from archtwin.audit.service import GENESIS, _hashable, chain_hash, verify_events
from archtwin.common import crypto
from archtwin.common.egress import EgressDenied, check_url
from archtwin.common.logging import redact, redact_text


def kp():
    return crypto.LocalKeyProvider(base64.b64encode(b"x" * 32).decode(), "test-v1")


def test_envelope_roundtrip_and_unique_ciphertexts():
    k = kp()
    a, b = crypto.seal({"password": "s3cret"}, "o/p/1", k), crypto.seal({"password": "s3cret"}, "o/p/1", k)
    assert a.ciphertext != b.ciphertext and b"s3cret" not in a.ciphertext
    assert crypto.open_envelope(a, "o/p/1", k) == {"password": "s3cret"}


def test_envelope_bound_to_scope_aad():
    k = kp()
    env = crypto.seal({"t": 1}, "orgA/projA/1", k)
    with pytest.raises(InvalidTag):
        crypto.open_envelope(env, "orgB/projB/1", k)


def test_bad_kek_rejected():
    with pytest.raises(RuntimeError):
        crypto.LocalKeyProvider(base64.b64encode(b"short").decode(), "x")


def fake_resolver(mapping):
    return lambda host: [ipaddress.ip_address(mapping[host])]


@pytest.mark.parametrize("url,ip", [("http://localhost/", "127.0.0.1"), ("http://meta/", "169.254.169.254"), ("http://intra/", "10.1.2.3"),
                                    ("http://v6/", "::1"), ("http://mapped/", "::ffff:127.0.0.1"), ("http://zero/", "0.0.0.0"),
                                    ("http://rebind.example/", "192.168.1.5")])
def test_private_and_metadata_ranges_denied(url, ip):
    host = url.split("/")[2]
    with pytest.raises(EgressDenied):
        check_url(url, allow_hosts=set(), resolver=fake_resolver({host: ip}))


@pytest.mark.parametrize("url", ["file:///etc/passwd", "gopher://x/", "http://user:pass@example.com/", "http://metadata.google.internal/"])
def test_schemes_credentials_and_metadata_names_denied(url):
    with pytest.raises(EgressDenied):
        check_url(url, allow_hosts=set(), resolver=fake_resolver({"example.com": "93.184.216.34", "metadata.google.internal": "169.254.169.254"}))


def test_public_and_allowlisted_private_hosts_allowed():
    check_url("https://example.com/x", allow_hosts=set(), resolver=fake_resolver({"example.com": "93.184.216.34"}))
    check_url("http://docker-proxy:2375/info", allow_hosts={"docker-proxy"}, resolver=fake_resolver({}))


def _chain(n=4):
    evs, prev = [], GENESIS
    for i in range(1, n + 1):
        e = {"id": uuid.uuid4(), "org_id": uuid.uuid4(), "seq": i, "occurred_at": "2026-11-08T00:00:00+00:00", "actor_id": None,
             "actor_name": "system", "action": f"a{i}", "resource_kind": "x", "resource_id": str(i), "project_id": None,
             "decision": "allow", "trace_id": "", "details": {"i": i}}
        h = chain_hash(prev, _hashable(e))
        evs.append({**e, "prev_hash": prev, "hash": h})
        prev = h
    return evs


def test_audit_chain_verifies():
    assert verify_events(_chain())["ok"]


def test_audit_tamper_detected():
    evs = _chain()
    evs[1]["details"] = {"i": 999}
    r = verify_events(evs)
    assert not r["ok"] and any("tampered" in p["problem"] for p in r["problems"])


def test_audit_gap_detected():
    evs = _chain()
    del evs[2]
    assert not verify_events(evs)["ok"]


def test_canary_secret_redacted_everywhere():
    blob = {"msg": "token ARCHTWIN-CANARY-abc123 and sk-livekey1234567890abcd", "password": "x",
            "url": "postgresql://u:pw@db:5432/x", "nested": [{"api_key": "k"}]}
    s = str(redact(blob))
    assert "CANARY" not in s and "sk-live" not in s and "pw@" not in s and "'k'" not in s
    assert redact_text("Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJlLXZhbHVlLXg") .count("REDACTED") == 1

import os
import time
import uuid

import httpx
import pytest

API = os.environ.get("ARCHTWIN_E2E_API", "http://localhost:8200/api/v1")
KC = os.environ.get("ARCHTWIN_E2E_KEYCLOAK", "http://localhost:8280/realms/archtwin/protocol/openid-connect/token")
PASSWORDS = {"admin": "admin", "alice": "archtwin", "bob": "archtwin", "vera": "archtwin", "mallory": "archtwin"}


class Client:
    def __init__(self, user: str):
        r = httpx.post(KC, data={"grant_type": "password", "client_id": "archtwin-cli", "username": user, "password": PASSWORDS[user]}, timeout=20)
        r.raise_for_status()
        self.user = user
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        self.c = httpx.Client(base_url=API, headers=self.h, timeout=180, transport=httpx.HTTPTransport(retries=2))

    def __getattr__(self, m):
        return getattr(self.c, m)

    def ok(self, method: str, path: str, status: int = 200, **kw):
        r = self.c.request(method, path, **kw)
        assert r.status_code == status, f"{method} {path} -> {r.status_code} {r.text[:400]}"
        return r.json() if r.headers.get("content-type", "").startswith(("application/json", "application/problem+json")) else r.text


def wait(fn, timeout=180, every=2.0, what="condition"):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        last = fn()
        if last:
            return last
        time.sleep(every)
    raise AssertionError(f"timed out waiting for {what}: {last!r}")


@pytest.fixture(scope="session")
def users():
    cs = {u: Client(u) for u in PASSWORDS}
    for c in cs.values():
        c.ok("GET", "/me")                       # first login onboards the user
    return cs


@pytest.fixture(scope="session")
def run_id():
    return uuid.uuid4().hex[:6]

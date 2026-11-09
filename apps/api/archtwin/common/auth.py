"""OIDC bearer-token validation against Keycloak JWKS (AT-IDENTITY_POLICY-001). 401 happens before any DB access."""
import asyncio
import time
from dataclasses import dataclass

import httpx
import jwt

from archtwin.common.errors import problem
from archtwin.common.logging import log
from archtwin.config import settings

JWKS_TTL_S = 300


@dataclass(frozen=True)
class Identity:
    subject: str
    username: str
    email: str | None
    display_name: str
    realm_roles: frozenset[str]


class Jwks:
    def __init__(self) -> None:
        self._keys: dict[str, object] = {}
        self._fetched = 0.0
        self._lock = asyncio.Lock()

    async def key(self, kid: str):
        age = time.monotonic() - self._fetched
        if kid in self._keys and age < JWKS_TTL_S:
            return self._keys[kid]
        async with self._lock:
            age = time.monotonic() - self._fetched
            # refresh on TTL expiry or on an unknown kid (key rotation), but at most every 10 s
            if age >= JWKS_TTL_S or (kid not in self._keys and age > 10):
                await self._refresh()
        if kid not in self._keys:
            raise problem(401, "AT-AUTH-001", "Invalid token", "unknown signing key")
        return self._keys[kid]

    async def _refresh(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(settings().oidc_jwks_url)
                r.raise_for_status()
            ks = jwt.PyJWKSet.from_dict(r.json())
            self._keys = {k.key_id: k.key for k in ks.keys}
            self._fetched = time.monotonic()
        except Exception as e:
            log.warning("jwks_fetch_failed", error=type(e).__name__)
            raise problem(503, "AT-AUTH-002", "Identity provider unavailable", retryable=True) from e

    def set_static(self, keys: dict[str, object]) -> None:   # tests
        self._keys, self._fetched = keys, time.monotonic()


jwks = Jwks()


async def verify(token: str) -> Identity:
    s = settings()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise problem(401, "AT-AUTH-001", "Invalid token", "malformed token") from e
    if header.get("alg") != "RS256":
        raise problem(401, "AT-AUTH-001", "Invalid token", "unsupported algorithm")
    key = await jwks.key(header.get("kid", ""))
    try:
        c = jwt.decode(token, key=key, algorithms=["RS256"], audience=s.oidc_audience, issuer=s.oidc_issuer,
                       options={"require": ["exp", "iss", "sub", "aud"]}, leeway=10)
    except jwt.ExpiredSignatureError as e:
        raise problem(401, "AT-AUTH-001", "Token expired") from e
    except jwt.PyJWTError as e:
        raise problem(401, "AT-AUTH-001", "Invalid token", str(e)) from e
    realm = c.get("realm_access") if isinstance(c.get("realm_access"), dict) else {}
    uname = c.get("preferred_username") or c["sub"]
    name = c.get("name") or " ".join(x for x in (c.get("given_name"), c.get("family_name")) if x) or uname
    return Identity(subject=c["sub"], username=uname, email=c.get("email"), display_name=name,
                    realm_roles=frozenset(realm.get("roles") or []))

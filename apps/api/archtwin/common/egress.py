"""Egress guard for connector HTTP calls (AT-CONNECTOR_PLATFORM, SSRF suite).

Denies loopback, link-local (incl. cloud metadata 169.254.169.254), private, multicast and reserved ranges unless the
host name is explicitly allow-listed by the operator (ARCHTWIN_EGRESS_ALLOW_PRIVATE_HOSTS, e.g. in-cluster services).
Redirects are never followed automatically: each hop is re-checked. Resolved addresses are checked before connecting.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

from archtwin.common.errors import problem
from archtwin.config import settings

METADATA_HOSTS = {"metadata.google.internal", "metadata", "instance-data"}
MAX_REDIRECTS = 3


class EgressDenied(Exception):
    pass


def _ip_blocked(ip: ipaddress._BaseAddress) -> bool:
    return (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved
            or ip.is_unspecified or (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None
                                     and _ip_blocked(ip.ipv4_mapped)))


def resolve(host: str) -> list[ipaddress._BaseAddress]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise EgressDenied(f"cannot resolve {host}") from e
    return [ipaddress.ip_address(i[4][0].split("%")[0]) for i in infos]


def check_url(url: str, allow_hosts: set[str] | None = None, resolver=None) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise EgressDenied(f"scheme {parts.scheme!r} not allowed")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise EgressDenied("missing host")
    if parts.username or parts.password:
        raise EgressDenied("credentials in URL are not allowed")
    allow = allow_hosts if allow_hosts is not None else settings().private_host_allowlist
    if host in allow:
        return
    if host in METADATA_HOSTS:
        raise EgressDenied("metadata endpoints are blocked")
    for ip in (resolver or resolve)(host):
        if _ip_blocked(ip):
            raise EgressDenied(f"{host} resolves to a blocked address range")


async def guarded_get(url: str, *, headers: dict | None = None, timeout: float = 20, max_bytes: int = 20_000_000,
                      allow_hosts: set[str] | None = None) -> httpx.Response:
    for _ in range(MAX_REDIRECTS + 1):
        try:
            check_url(url, allow_hosts)
        except EgressDenied as e:
            raise problem(422, "AT-EGRESS-001", "Egress denied", str(e)) from e
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as c:
            r = await c.get(url, headers=headers or {})
        if r.is_redirect and "location" in r.headers:
            url = urljoin(url, r.headers["location"])
            continue
        if len(r.content) > max_bytes:
            raise problem(422, "AT-EGRESS-002", "Response too large")
        return r
    raise problem(422, "AT-EGRESS-003", "Too many redirects")

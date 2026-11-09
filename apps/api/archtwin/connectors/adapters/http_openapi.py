"""Live OpenAPI connector: fetches a running service's OpenAPI document through the egress guard (origin = runtime)."""
from __future__ import annotations

import hashlib
from typing import Any

import yaml

from archtwin.common.egress import guarded_get
from archtwin.connectors.sdk import ScanResult, TestResult

V = "openapi-http/1.0"


class HttpOpenApiConnector:
    kind = "http_openapi"
    flag = "connector.http_openapi"
    manifest = {"name": "HTTP OpenAPI (live contract)", "origin": "runtime", "scopes": ["GET openapi document"],
                "freshness_sla_s": 86400,
                "config": {"url": "https://service/openapi.json", "system": "", "service": "compose service name"}}

    async def _fetch(self, cfg: dict[str, Any], secret: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {secret['token']}"} if secret.get("token") else {}
        r = await guarded_get(str(cfg["url"]), headers=headers)
        r.raise_for_status()
        return yaml.safe_load(r.text)

    async def test(self, cfg: dict[str, Any], secret: dict[str, Any]) -> TestResult:
        try:
            d = await self._fetch(cfg, secret)
            return TestResult(ok=True, scopes=self.manifest["scopes"], details={"title": (d.get("info") or {}).get("title"),
                                                                                  "paths": len(d.get("paths") or {})})
        except Exception as e:  # noqa: BLE001
            return TestResult(ok=False, warnings=[str(getattr(e, "detail", e))[:300]])

    async def scan(self, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None) -> ScanResult:
        d = await self._fetch(cfg, secret)
        system, service = cfg.get("system") or "external", cfg.get("service") or "api"
        raw = yaml.safe_dump(d, sort_keys=True)
        r = ScanResult(revision=hashlib.sha256(raw.encode()).hexdigest()[:16])
        info = d.get("info") or {}
        ck = f"contract:{system}/{service}/live"
        ckey = f"container:{system}/{service}"
        r.node("runtime", ck, "api-contract", str(info.get("title", "API")), V, attrs={"version": str(info.get("version", "")),
               "format": "openapi", "url": cfg["url"]}, ref=str(cfg["url"]))
        r.edge("runtime", ckey, "implements", ck, V, ref=str(cfg["url"]))
        for p, ops in (d.get("paths") or {}).items():
            for m in ops or {}:
                if m.lower() in ("get", "post", "put", "patch", "delete"):
                    ek = f"endpoint:{system}/{service}/{m.upper()} {p}"
                    r.node("runtime", ek, "api-endpoint", f"{m.upper()} {p}", V, attrs={"method": m.upper(), "path": p, "served": True,
                           "summary": str((ops[m] or {}).get("summary", ""))[:200]}, ref=str(cfg["url"]))
                    r.edge("runtime", ckey, "exposes", ek, V, ref=str(cfg["url"]))
        r.coverage = {"origin": "runtime", "prefixes": [f"endpoint:{system}/{service}/"]}
        r.stats = {"endpoints": len([o for o in r.observations if o.kind == "api-endpoint"])}
        return r

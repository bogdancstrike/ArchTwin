"""OpenTelemetry service-graph connector (read-only — AT-RUNTIME_DISCOVERY, phase-02 task 4.3).

Reads the OTel Collector `servicegraph` connector metrics from Prometheus' HTTP API (no agents, reuse existing telemetry):
  traces_service_graph_request_total{client, server, connection_type}
  traces_service_graph_request_failed_total
  traces_service_graph_request_server_seconds_bucket   (p95 latency)
and turns them into runtime `calls` edges with a time window, request rate and error rate.

Identity: an OTel `service.name` maps to `container:{system}/{service.name}` (fixture and Compose convention), unless
`service_map` overrides it. Virtual peers (databases, brokers) become `writes`/`publishes` edges to the peer service when
it is mapped, else they are reported as unmapped and stay UNKNOWN — never invented.
"""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlencode

from archtwin.common.egress import EgressDenied, check_url, guarded_get
from archtwin.connectors.sdk import ScanResult, TestResult

V = "otel-servicegraph/1.0"


async def _query(base: str, q: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    r = await guarded_get(f"{base}/api/v1/query?{urlencode({'query': q})}", headers=headers, timeout=20)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "success":
        raise RuntimeError(body.get("error", "prometheus query failed"))
    return body["data"]["result"]


class OtelServiceGraphConnector:
    kind = "otel_servicegraph"
    flag = "connector.opentelemetry"
    manifest = {"name": "OpenTelemetry service graph (Prometheus)", "category": "runtime", "origin": "runtime",
                "scopes": ["Prometheus HTTP API: query (read-only)"], "freshness_sla_s": 900,
                "config": {"prometheus_url": "http://prometheus:9090", "system": "system the services belong to",
                           "window": "15m", "min_rate": 0.0, "metric_prefix": "traces_service_graph",
                           "service_map": {"<otel service.name>": "<compose service>"},
                           "peer_map": {"<virtual peer, e.g. orders>": "<compose service, e.g. orders-db>"}},
                "secret": {"bearer_token": "optional"}}

    def _base(self, cfg: dict[str, Any]) -> str:
        url = str(cfg.get("prometheus_url") or "").rstrip("/")
        check_url(url or "http://")
        return url

    @staticmethod
    def _headers(secret: dict[str, Any]) -> dict[str, str]:
        return {"Authorization": f"Bearer {secret['bearer_token']}"} if secret.get("bearer_token") else {}

    async def test(self, cfg: dict[str, Any], secret: dict[str, Any]) -> TestResult:
        try:
            base = self._base(cfg)
            prefix = cfg.get("metric_prefix") or "traces_service_graph"
            res = await _query(base, f"count({prefix}_request_total)", self._headers(secret))
            n = int(float(res[0]["value"][1])) if res else 0
            warnings = [] if n else [f"no {prefix}_request_total series: is the collector servicegraph connector exported to this Prometheus?"]
            bi = await guarded_get(f"{base}/api/v1/status/buildinfo", headers=self._headers(secret), timeout=10)
            return TestResult(ok=True, scopes=self.manifest["scopes"], warnings=warnings,
                              details={"series": n, "prometheus_version": (bi.json().get("data") or {}).get("version") if bi.is_success else None})
        except EgressDenied as e:
            return TestResult(ok=False, warnings=[str(e)])
        except Exception as e:  # noqa: BLE001
            return TestResult(ok=False, warnings=[f"{type(e).__name__}: {str(getattr(e, 'detail', e))[:200]}"])

    async def scan(self, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None) -> ScanResult:
        base = self._base(cfg)
        h = self._headers(secret)
        prefix = cfg.get("metric_prefix") or "traces_service_graph"
        window = str(cfg.get("window") or "15m")
        if not window[:-1].isdigit() or window[-1] not in "smhd":
            raise ValueError("window must look like 15m / 1h")
        system = cfg.get("system") or "external"
        smap: dict[str, str] = dict(cfg.get("service_map") or {})
        pmap: dict[str, str] = dict(cfg.get("peer_map") or {})
        min_rate = float(cfg.get("min_rate") or 0)
        by = "client, server, connection_type"
        total = await _query(base, f"sum by ({by}) (increase({prefix}_request_total[{window}]))", h)
        failed = {self._k(m["metric"]): float(m["value"][1])
                  for m in await _query(base, f"sum by ({by}) (increase({prefix}_request_failed_total[{window}]))", h)}
        p95 = {self._k(m["metric"]): float(m["value"][1]) for m in await _query(
            base, f"histogram_quantile(0.95, sum by ({by}, le) (rate({prefix}_request_server_seconds_bucket[{window}])))", h)}
        r = ScanResult(revision=f"window:{window}@{int(time.time())}")
        seen_services: set[str] = set()
        unmapped: set[str] = set()

        def svc_key(name: str) -> str:
            seen_services.add(name)
            return f"container:{system}/{smap.get(name, name)}"

        for m in total:
            lab = m["metric"]
            client, server, ctype = lab.get("client", ""), lab.get("server", ""), lab.get("connection_type", "")
            count = float(m["value"][1])
            secs = _seconds(window)
            if not client or not server or count / secs < min_rate or count <= 0:
                continue
            if client == "unknown" or server == "unknown":
                unmapped.add(f"{client}->{server}")
                continue
            k = self._k(lab)
            attrs = {"requests": round(count), "rate_per_s": round(count / secs, 4), "window": window,
                     "errors": round(failed.get(k, 0)), "error_rate": round(failed.get(k, 0) / count, 4) if count else 0,
                     "p95_ms": round(p95[k] * 1000, 1) if p95.get(k) == p95.get(k) and k in p95 else None,
                     "otel_client": client, "otel_server": server, "connection_type": ctype or "direct"}
            src = svc_key(client)
            if ctype in ("", "direct"):
                r.edge("runtime", src, "calls", svc_key(server), V, attrs={**attrs, "protocols": ["http"]},
                       ref=f"{base}/graph?{prefix}", confidence=0.95)
            elif ctype == "messaging_system":
                r.edge("runtime", src, "publishes", svc_key(server), V, attrs={**attrs, "protocols": ["messaging"]},
                       ref=f"{base}/graph?{prefix}", confidence=0.9)
            else:                                                      # virtual_node / database peers
                target = pmap.get(server)
                if not target:
                    unmapped.add(f"{client}->{server} ({ctype})")
                    continue
                rel = "writes" if ctype == "database" else "calls"
                r.edge("runtime", src, rel, f"container:{system}/{target}", V, attrs={**attrs, "peer": server}, ref=f"{base}/graph?{prefix}",
                       confidence=0.9)
        for name in sorted(seen_services):
            r.node("runtime", f"container:{system}/{smap.get(name, name)}", "container", smap.get(name, name), V,
                   attrs={"otel_service_name": name, "traced": True}, ref=f"otel:service/{name}", confidence=0.9)
        if unmapped:
            r.warnings.append("unmapped peers (kept UNKNOWN; add peer_map entries): " + ", ".join(sorted(unmapped))[:400])
        r.stats = {"edges": len([o for o in r.observations if o.subject_kind == "edge"]), "services": len(seen_services),
                   "unmapped": len(unmapped), "window": window}
        # Runtime absence from traces is not proof of absence (sampling, idle services): coverage is limited to edges we saw.
        r.coverage = {"origin": "runtime", "prefixes": [], "edges_only": True}
        return r

    @staticmethod
    def _k(lab: dict[str, str]) -> tuple[str, str, str]:
        return lab.get("client", ""), lab.get("server", ""), lab.get("connection_type", "")


def _seconds(window: str) -> float:
    return float(window[:-1]) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[window[-1]]

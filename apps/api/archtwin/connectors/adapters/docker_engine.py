"""Docker Engine runtime connector (read-only, through tecnativa/docker-socket-proxy with POST disabled).

Observes running/stopped containers. Compose labels give the canonical identity `container:<project>/<service>`, the same
key the compose analyzer emits, so static and runtime evidence reconcile without fuzzy matching (spike S3).
"""
from __future__ import annotations

from typing import Any

from archtwin.common.egress import guarded_get
from archtwin.connectors.analyzers.common import classify
from archtwin.connectors.sdk import ScanResult, TestResult

V = "docker-engine/1.0"


class DockerEngineConnector:
    kind = "docker"
    flag = "connector.docker"
    manifest = {"name": "Docker Engine (runtime)", "origin": "runtime", "scopes": ["containers:list", "networks:list"],
                "freshness_sla_s": 900,
                "config": {"endpoint": "Docker API proxy URL, e.g. http://docker-proxy:2375",
                           "compose_projects": "list of compose project names to include (empty = all)"}}

    async def _get(self, cfg: dict[str, Any], path: str):
        base = str(cfg.get("endpoint") or "http://docker-proxy:2375").rstrip("/")
        r = await guarded_get(f"{base}{path}", timeout=10)
        r.raise_for_status()
        return r.json()

    async def test(self, cfg: dict[str, Any], secret: dict[str, Any]) -> TestResult:
        try:
            info = await self._get(cfg, "/info")
            warnings = []
            try:   # a write probe must FAIL: the proxy has to block POST (excess privilege check)
                import httpx
                base = str(cfg.get("endpoint") or "http://docker-proxy:2375").rstrip("/")
                async with httpx.AsyncClient(timeout=5) as c:
                    w = await c.post(f"{base}/containers/archtwin-probe-nonexistent/stop")
                if w.status_code not in (401, 403, 405):
                    warnings.append(f"Docker API accepts write calls (HTTP {w.status_code}); use a read-only proxy")
            except Exception:  # noqa: BLE001
                pass
            return TestResult(ok=True, scopes=self.manifest["scopes"], warnings=warnings,
                              details={"server_version": info.get("ServerVersion"), "containers": info.get("Containers")})
        except Exception as e:  # noqa: BLE001
            return TestResult(ok=False, warnings=[str(getattr(e, "detail", e))[:300]])

    async def scan(self, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None) -> ScanResult:
        containers = await self._get(cfg, "/containers/json?all=1")
        wanted = set(cfg.get("compose_projects") or [])
        r = ScanResult(revision="")
        systems: set[str] = set()
        for c in containers:
            labels = c.get("Labels") or {}
            proj, svc = labels.get("com.docker.compose.project"), labels.get("com.docker.compose.service")
            if wanted and proj not in wanted:
                continue
            name = (c.get("Names") or ["/unknown"])[0].lstrip("/")
            key = f"container:{proj}/{svc}" if proj and svc else f"container:docker/{name}"
            system = proj or "docker"
            if system not in systems:
                systems.add(system)
                r.node("runtime", f"system:{system}", "software-system", system, V, attrs={"runtime": "docker"},
                       ref=f"docker:/compose/{system}")
            sub, tech = classify(c.get("Image", ""), svc or name)
            state = c.get("State", "")
            r.node("runtime", key, "container", svc or name, V, ref=f"docker:/containers/{c.get('Id', '')[:12]}",
                   attrs={"state": state, "status": c.get("Status", ""), "image": c.get("Image", ""),
                          "image_id": (c.get("ImageID") or "")[:19], "container_name": name, "subtype": sub, "technology": tech,
                          "networks": sorted((c.get("NetworkSettings") or {}).get("Networks", {}).keys()),
                          "ports": sorted({f"{p.get('IP', '')}:{p.get('PublicPort')}->{p.get('PrivatePort')}"
                                           for p in c.get("Ports") or [] if p.get("PublicPort")}),
                          "running": state == "running", "one_shot_exited_ok": state == "exited" and "Exited (0)" in c.get("Status", "")},
                   span={"container_id": c.get("Id", "")[:12]}, confidence=1.0)
            r.edge("runtime", f"system:{system}", "contains", key, V, ref=f"docker:/compose/{system}")
        r.coverage = {"origin": "runtime", "systems": sorted(systems),
                      "prefixes": [f"container:{s}/" for s in sorted(systems)] + [f"system:{s}" for s in sorted(systems)]}
        if wanted:   # wanted projects with zero containers are still covered: absence there is meaningful
            r.coverage["systems"] = sorted(systems | wanted)
            r.coverage["prefixes"] = sorted(set(r.coverage["prefixes"]) | {f"container:{s}/" for s in wanted})
        r.stats = {"containers": len(containers), "observed": len([o for o in r.observations if o.kind == "container"])}
        return r

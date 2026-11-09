"""GitHub connector (read-only — AT-SOURCE_CODE_DISCOVERY, AT-WORK_CONNECTORS; phase-02 tasks 3.1 and 6.1).

Per configured repository: metadata, default branch + selected branches, open/recent pull requests and issues (as
`work-item` nodes, origin `issue`), and the code itself (cloned read-only and run through the same analyzers as the
generic Git connector, origin `static`). Push/PR webhooks trigger incremental scans (see `connectors.webhooks`).

Write-back is structurally absent (task 6.3): there is no write call in this module, and `test` warns when the token holds
write/admin scopes so an organization policy can refuse activation.
"""
from __future__ import annotations

import re
from typing import Any

from archtwin.common.egress import EgressDenied, check_url, guarded_get
from archtwin.connectors.adapters.git_repo import GitRepoConnector
from archtwin.connectors.sdk import ScanResult, TestResult

V = "github-rest/1.0"
API = "https://api.github.com"
REPO_RX = re.compile(r"^[A-Za-z0-9_.\-]{1,100}/[A-Za-z0-9_.\-]{1,100}$")
WRITE_SCOPES = re.compile(r"^(repo|public_repo|workflow|delete_repo|write:.*|admin:.*)$")
CLOSES_RX = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", re.IGNORECASE)
MAX_PAGES = 5


class RateLimited(Exception):
    pass


class GitHubConnector:
    kind = "github"
    flag = "connector.github"
    manifest = {"name": "GitHub", "category": "code", "origin": "static",
                "scopes": ["metadata:read", "contents:read", "issues:read", "pull_requests:read"], "freshness_sla_s": 86400,
                "webhooks": ["push", "pull_request", "issues"],
                "config": {"repos": ["owner/name"], "api_url": API, "branches": ["main"], "issues": True, "pull_requests": True,
                           "analyze_code": True, "max_items": 200, "system_names": {"owner/name": "system name override"}},
                "secret": {"token": "fine-grained token with read-only Contents/Issues/Pull requests/Metadata",
                           "webhook_secret": "optional — verifies X-Hub-Signature-256"}}

    def _api(self, cfg: dict[str, Any]) -> str:
        url = str(cfg.get("api_url") or API).rstrip("/")
        check_url(url)
        return url

    @staticmethod
    def _h(secret: dict[str, Any]) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "archtwin-connector"}
        if secret.get("token"):
            h["Authorization"] = f"Bearer {secret['token']}"
        return h

    async def _get(self, url: str, secret: dict[str, Any]):
        r = await guarded_get(url, headers=self._h(secret), timeout=20)
        if r.status_code == 403 and r.headers.get("x-ratelimit-remaining") == "0":
            raise RateLimited(r.headers.get("x-ratelimit-reset", ""))
        return r

    async def _paged(self, url: str, secret: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for _ in range(MAX_PAGES):
            r = await self._get(url, secret)
            r.raise_for_status()
            out.extend(r.json())
            nxt = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get("link", ""))
            if not nxt or len(out) >= limit:
                break
            url = nxt.group(1)
        return out[:limit]

    def _repos(self, cfg: dict[str, Any]) -> list[str]:
        repos = [str(x) for x in cfg.get("repos") or []]
        bad = [x for x in repos if not REPO_RX.match(x)]
        if not repos or bad:
            raise ValueError(f"repos must be a non-empty list of owner/name ({', '.join(bad)})")
        return repos

    async def test(self, cfg: dict[str, Any], secret: dict[str, Any]) -> TestResult:
        try:
            api, repos = self._api(cfg), self._repos(cfg)
            warnings: list[str] = []
            scopes: list[str] = []
            details: dict[str, Any] = {"repos": {}}
            if secret.get("token"):
                u = await self._get(f"{api}/user", secret)
                if u.status_code == 401:
                    return TestResult(ok=False, warnings=["token rejected by GitHub (401)"])
                scopes = [s.strip() for s in (u.headers.get("x-oauth-scopes") or "").split(",") if s.strip()]
                details["token_type"] = "classic" if "x-oauth-scopes" in u.headers else "fine-grained/app"
                excess = [s for s in scopes if WRITE_SCOPES.match(s)]
                if excess:
                    warnings.append(f"token has write/admin scopes {excess}: create a read-only fine-grained token")
            for full in repos:
                rr = await self._get(f"{api}/repos/{full}", secret)
                if rr.status_code != 200:
                    details["repos"][full] = f"HTTP {rr.status_code}"
                    warnings.append(f"{full}: not accessible (HTTP {rr.status_code})")
                    continue
                j = rr.json()
                perms = j.get("permissions") or {}
                details["repos"][full] = {"private": j.get("private"), "default_branch": j.get("default_branch"),
                                          "permissions": {k: v for k, v in perms.items() if v}}
                if perms.get("admin") or perms.get("push") or perms.get("maintain"):
                    warnings.append(f"{full}: credentials can push/administer this repository — read access is enough")
            ok = any(isinstance(v, dict) for v in details["repos"].values())
            return TestResult(ok=ok, scopes=scopes or self.manifest["scopes"], warnings=warnings, details=details)
        except (EgressDenied, ValueError) as e:
            return TestResult(ok=False, warnings=[str(e)])
        except RateLimited:
            return TestResult(ok=False, warnings=["GitHub rate limit exhausted; try again later or supply a token"])
        except Exception as e:  # noqa: BLE001
            return TestResult(ok=False, warnings=[f"{type(e).__name__}: {str(getattr(e, 'detail', e))[:200]}"])

    async def scan(self, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None) -> ScanResult:
        api, repos = self._api(cfg), self._repos(cfg)
        limit = min(int(cfg.get("max_items") or 200), 1000)
        names = dict(cfg.get("system_names") or {})
        out = ScanResult()
        revs = []
        for full in repos:
            system = names.get(full) or full.split("/")[1]
            try:
                r = await self._scan_repo(api, full, system, cfg, secret, ref, limit)
            except RateLimited:
                out.complete = False
                out.warnings.append(f"{full}: rate limited — partial scan, unseen items kept (not tombstoned)")
                continue
            out.observations += r.observations
            out.documents += r.documents
            out.warnings += r.warnings
            out.complete = out.complete and r.complete
            revs.append((full, r.revision))
            for k, v in r.stats.items():
                if isinstance(v, int | float):
                    out.stats[k] = out.stats.get(k, 0) + v
            cov = r.coverage or {}
            out.coverage.setdefault("prefixes", []).extend(cov.get("prefixes", []))
            out.coverage.setdefault("systems", []).extend(cov.get("systems", []))
        out.coverage["origin"] = "static"
        out.revision = revs[0][1] if len(revs) == 1 else ",".join(f"{f}@{rv[:12]}" for f, rv in revs)
        return out

    async def _scan_repo(self, api: str, full: str, system: str, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None,
                         limit: int) -> ScanResult:
        rr = await self._get(f"{api}/repos/{full}", secret)
        rr.raise_for_status()
        repo = rr.json()
        default = repo.get("default_branch") or "main"
        r = ScanResult()
        if cfg.get("analyze_code", True):
            code = await GitRepoConnector().scan({"url": repo["clone_url"], "name": system}, {"token": secret.get("token", "")}, ref or default)
            r.observations, r.documents, r.revision = code.observations, code.documents, code.revision
            r.coverage, r.stats, r.warnings = code.coverage, dict(code.stats), list(code.warnings)
        else:
            head = (await self._get(f"{api}/repos/{full}/commits/{ref or default}", secret)).json()
            r.revision = head.get("sha", "")
        sk = f"system:{system}"
        r.node("static", sk, "software-system", system, V, ref=repo.get("html_url", ""),
               attrs={"github": full, "description": repo.get("description") or "", "default_branch": default,
                      "visibility": repo.get("visibility"), "topics": repo.get("topics", []), "language": repo.get("language"),
                      "archived": repo.get("archived", False), "pushed_at": repo.get("pushed_at")})
        branches = [b for b in await self._paged(f"{api}/repos/{full}/branches?per_page=100", secret, 300)]
        wanted = set(cfg.get("branches") or []) | {default}
        r.stats["branches"] = len(branches)
        r.node("static", f"{sk}#branches", "document", f"{system} branches", V, ref=f"{repo.get('html_url', '')}/branches",
               attrs={"branches": [{"name": b["name"], "sha": b["commit"]["sha"], "protected": b.get("protected", False)}
                                   for b in branches if b["name"] in wanted][:50], "total": len(branches)}, confidence=1.0)
        if cfg.get("issues", True):
            issues = [i for i in await self._paged(f"{api}/repos/{full}/issues?state=all&sort=updated&per_page=100", secret, limit)
                      if "pull_request" not in i]
            for i in issues:
                self._work_item(r, full, system, i, "issue")
            r.stats["issues"] = len(issues)
        if cfg.get("pull_requests", True):
            prs = await self._paged(f"{api}/repos/{full}/pulls?state=all&sort=updated&direction=desc&per_page=100", secret, limit)
            for p in prs:
                wk = self._work_item(r, full, system, p, "pull_request")
                for n in sorted({int(x) for x in CLOSES_RX.findall(f"{p.get('title', '')}\n{p.get('body') or ''}")}):
                    r.edge("issue", wk, "implements", f"work-item:github/{full}#{n}", V, attrs={"detected_by": "closing keyword"},
                           ref=p.get("html_url", ""), confidence=1.0)
            r.stats["pull_requests"] = len(prs)
        r.coverage.setdefault("prefixes", []).append(f"work-item:github/{full}#")
        return r

    @staticmethod
    def _work_item(r: ScanResult, full: str, system: str, i: dict[str, Any], typ: str) -> str:
        wk = f"work-item:github/{full}#{i['number']}"
        attrs = {"provider": "github", "type": typ, "number": i["number"], "state": i.get("state"), "url": i.get("html_url"),
                 "labels": [lb["name"] for lb in i.get("labels", [])], "assignees": [a["login"] for a in i.get("assignees") or []],
                 "author": (i.get("user") or {}).get("login"), "created_at": i.get("created_at"), "updated_at": i.get("updated_at"),
                 "closed_at": i.get("closed_at")}
        if typ == "pull_request":
            attrs.update({"merged_at": i.get("merged_at"), "draft": i.get("draft", False),
                          "head": {"ref": (i.get("head") or {}).get("ref"), "sha": (i.get("head") or {}).get("sha")},
                          "base": (i.get("base") or {}).get("ref"), "merge_commit_sha": i.get("merge_commit_sha")})
        r.node("issue", wk, "work-item", f"#{i['number']} {i.get('title', '')}"[:400], V, attrs=attrs, ref=i.get("html_url", ""))
        r.edge("issue", wk, "references", f"system:{system}", V, ref=i.get("html_url", ""))
        return wk

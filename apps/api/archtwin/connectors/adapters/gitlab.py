"""GitLab connector (read-only — AT-SOURCE_CODE_DISCOVERY, AT-WORK_CONNECTORS; phase-02 tasks 3.1 and 6.1). Self-hosted or gitlab.com.

Per configured project (or every project of a configured group): metadata, default + selected branches, issues and merge
requests (as `work-item` nodes, origin `issue`), and the code itself (cloned read-only at any ref and run through the same
analyzers as the local/Git connector, origin `static`). Push / merge-request / issue webhooks trigger incremental scans
(see `connectors.webhooks`, verified with X-Gitlab-Token).

Uses the GitLab REST API v4 directly through the egress guard (every hop SSRF-checked) rather than python-gitlab, whose
`requests` transport would bypass it — same approach as the GitHub adapter.
Write-back is structurally absent (task 6.3): there is no write call in this module, and `test` warns when the token holds
write scopes (`api`, `write_*`, `sudo`, …) or Developer+ access so an organization policy can refuse activation.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urlsplit

from archtwin.common.egress import EgressDenied, check_url, guarded_get, tls_verify
from archtwin.connectors.adapters.git_repo import GitRepoConnector
from archtwin.connectors.sdk import ScanResult, TestResult

V = "gitlab-rest/1.0"
PATH_RX = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,254}(/[A-Za-z0-9_][A-Za-z0-9_.\-]{0,254}){0,19}$")
READ_SCOPES = {"read_api", "read_repository", "read_user", "read_registry", "read_package_registry", "read_virtual_registry",
               "openid", "profile", "email", "read_observability", "read_service_ping"}
CLOSES_RX = re.compile(r"\b(?:close[sd]?|closing|fix(?:e[sd]|ing)?|resolve[sd]?|resolving|implement(?:s|ed|ing)?)\s*:?\s+#(\d+)\b",
                       re.IGNORECASE)
REPORTER, DEVELOPER = 20, 30
MAX_PAGES = 10


class RateLimited(Exception):
    pass


def split_project(entry: str, base: str | None) -> tuple[str, str]:
    """`https://host/group/sub/proj[.git][/-/tree/x]` or `group/sub/proj` -> (base_url, path_with_namespace)."""
    entry = entry.strip()
    if entry.startswith(("https://", "http://")):
        u = urlsplit(entry)
        path = u.path.split("/-/", 1)[0].strip("/").removesuffix(".git")
        return f"{u.scheme}://{u.netloc}", path
    if not base:
        raise ValueError("url (GitLab base URL) is required when projects are given as paths")
    return base, entry.strip("/").removesuffix(".git")


def _wid(path: str, iid: int, typ: str) -> str:
    return f"work-item:gitlab/{path}{'!' if typ == 'merge_request' else '#'}{iid}"


class GitLabConnector:
    kind = "gitlab"
    flag = "connector.gitlab"
    manifest = {"name": "GitLab", "category": "code", "origin": "static",
                "scopes": ["read_api", "read_repository"], "freshness_sla_s": 86400,
                "webhooks": ["push", "merge_request", "issue"],
                "config": {"projects": ["https://gitlab.example.com/group/sub/project (or group/sub/project with url)"],
                           "url": "https://gitlab.example.com", "groups": ["group/sub — every project in it"],
                           "branches": ["main"], "issues": True, "merge_requests": True, "analyze_code": True, "max_items": 200,
                           "content": "auto | code | docs", "system_names": {"group/project": "system name override"}},
                "secret": {"token": "personal/project/group access token with read_api + read_repository (Reporter role)",
                           "webhook_secret": "optional — the webhook 'Secret token' (X-Gitlab-Token)"}}

    # ------------------------------------------------------------------ plumbing
    def _base(self, cfg: dict[str, Any]) -> str | None:
        b = str(cfg.get("url") or "").rstrip("/") or None
        if b:
            check_url(b)
        return b

    def _targets(self, cfg: dict[str, Any]) -> tuple[str, list[str], list[str]]:
        base = self._base(cfg)
        projects: list[str] = []
        for e in cfg.get("projects") or []:
            b, p = split_project(str(e), base)
            if base and b.rstrip("/") != base:
                raise ValueError(f"{e}: all projects must be on {base}")
            base = base or b
            projects.append(p)
        groups: list[str] = []
        for g in cfg.get("groups") or []:
            b, p = split_project(str(g), base)
            base = base or b
            groups.append(p)
        bad = [x for x in projects + groups if not PATH_RX.match(x) or ".." in x]
        if not (projects or groups) or bad:
            raise ValueError(f"projects/groups must be GitLab paths or URLs ({', '.join(bad) or 'none given'})")
        assert base is not None
        check_url(base)
        return base, projects, groups

    @staticmethod
    def _h(secret: dict[str, Any]) -> dict[str, str]:
        h = {"Accept": "application/json", "User-Agent": "archtwin-connector"}
        if secret.get("token"):
            h["PRIVATE-TOKEN"] = str(secret["token"])
        return h

    async def _get(self, url: str, secret: dict[str, Any], params: dict | None = None):
        r = await guarded_get(url, headers=self._h(secret), timeout=30, params=params)
        if r.status_code == 429:
            raise RateLimited(r.headers.get("retry-after", ""))
        return r

    async def _paged(self, url: str, secret: dict[str, Any], params: dict, limit: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        page = 1
        for _ in range(MAX_PAGES):
            r = await self._get(url, secret, {**params, "per_page": 100, "page": page})
            r.raise_for_status()
            out.extend(r.json())
            nxt = r.headers.get("x-next-page", "")
            if not nxt.isdigit() or len(out) >= limit:
                break
            page = int(nxt)
        return out[:limit]

    async def _project(self, api: str, path: str, secret: dict[str, Any]):
        return await self._get(f"{api}/projects/{quote(path, safe='')}", secret, {"statistics": "false"})

    async def _group_projects(self, api: str, group: str, secret: dict[str, Any]) -> list[str]:
        ps = await self._paged(f"{api}/groups/{quote(group, safe='')}/projects", secret,
                               {"include_subgroups": "true", "archived": "false", "order_by": "path", "sort": "asc", "simple": "true"}, 500)
        return [p["path_with_namespace"] for p in ps]

    async def _all_projects(self, api: str, projects: list[str], groups: list[str], secret: dict[str, Any]) -> list[str]:
        seen = list(dict.fromkeys(projects))
        for g in groups:
            for p in await self._group_projects(api, g, secret):
                if p not in seen:
                    seen.append(p)
        return seen

    # ------------------------------------------------------------------ test
    async def test(self, cfg: dict[str, Any], secret: dict[str, Any]) -> TestResult:
        try:
            base, projects, groups = self._targets(cfg)
            api = f"{base}/api/v4"
            warnings: list[str] = []
            scopes: list[str] = []
            details: dict[str, Any] = {"url": base, "projects": {}}
            if not tls_verify(base):
                warnings.append(f"TLS certificate of {urlsplit(base).hostname} is NOT verified (operator allow-list)")
            if base.startswith("http://") and secret.get("token"):
                warnings.append("plain-HTTP GitLab: the token travels unencrypted — use https")
            if secret.get("token"):
                u = await self._get(f"{api}/user", secret)
                if u.status_code == 401:
                    return TestResult(ok=False, warnings=["token rejected by GitLab (401)"])
                details["user"] = (u.json() or {}).get("username") if u.status_code == 200 else None
                t = await self._get(f"{api}/personal_access_tokens/self", secret)
                if t.status_code == 200:
                    tj = t.json()
                    scopes = list(tj.get("scopes") or [])
                    details["token_expires_at"] = tj.get("expires_at")
                    excess = [s for s in scopes if s not in READ_SCOPES]
                    if excess:
                        warnings.append(f"token has write/admin scopes {excess}: create a token with read_api + read_repository only")
                    if "read_repository" not in scopes and "api" not in scopes and cfg.get("analyze_code", True):
                        warnings.append("token lacks read_repository: code cannot be cloned")
            else:
                warnings.append("no token: only public projects are visible")
            try:
                every = await self._all_projects(api, projects, groups, secret)
            except RateLimited:
                raise
            except Exception as e:  # noqa: BLE001 — a group that cannot be listed is reported, projects still tested
                warnings.append(f"groups not listable: {type(e).__name__}")
                every = projects
            for path in every[:50]:
                rr = await self._project(api, path, secret)
                if rr.status_code != 200:
                    details["projects"][path] = f"HTTP {rr.status_code}"
                    warnings.append(f"{path}: not accessible (HTTP {rr.status_code})")
                    continue
                j = rr.json()
                perms = j.get("permissions") or {}
                level = max((perms.get("project_access") or {}).get("access_level") or 0, (perms.get("group_access") or {}).get("access_level") or 0)
                details["projects"][path] = {"id": j.get("id"), "visibility": j.get("visibility"), "default_branch": j.get("default_branch"),
                                             "access_level": level, "web_url": j.get("web_url")}
                if level >= DEVELOPER:
                    warnings.append(f"{path}: credentials can push (access level {level}) — Reporter ({REPORTER}) is enough")
            if len(every) > 50:
                details["projects_total"] = len(every)
            ok = any(isinstance(v, dict) for v in details["projects"].values())
            return TestResult(ok=ok, scopes=scopes or self.manifest["scopes"], warnings=warnings, details=details)
        except (EgressDenied, ValueError) as e:
            return TestResult(ok=False, warnings=[str(e)])
        except RateLimited:
            return TestResult(ok=False, warnings=["GitLab rate limit reached; try again later"])
        except Exception as e:  # noqa: BLE001
            return TestResult(ok=False, warnings=[f"{type(e).__name__}: {str(getattr(e, 'detail', e))[:200]}"])

    # ------------------------------------------------------------------ scan
    async def scan(self, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None) -> ScanResult:
        base, projects, groups = self._targets(cfg)
        api = f"{base}/api/v4"
        limit = min(int(cfg.get("max_items") or 200), 1000)
        names = dict(cfg.get("system_names") or {})
        every = await self._all_projects(api, projects, groups, secret)
        only: str | None = None
        if ref and "@" in ref:                        # webhook push: "<project path>@<sha>" scans that project only (partial)
            only, ref = ref.rsplit("@", 1)
            if only not in every:
                raise ValueError(f"{only} is not configured on this connector")
        out = ScanResult()
        revs = []
        for path in every:
            if only and path != only:
                continue
            system = names.get(path) or path.rsplit("/", 1)[-1]
            try:
                r = await self._scan_project(api, path, system, cfg, secret, ref, limit)
            except RateLimited:
                out.complete = False
                out.warnings.append(f"{path}: rate limited — partial scan, unseen items kept (not tombstoned)")
                continue
            out.observations += r.observations
            out.documents += r.documents
            out.warnings += r.warnings
            out.complete = out.complete and r.complete
            revs.append((path, r.revision))
            for k, v in r.stats.items():
                if isinstance(v, int | float):
                    out.stats[k] = out.stats.get(k, 0) + v
            cov = r.coverage or {}
            out.coverage.setdefault("prefixes", []).extend(cov.get("prefixes", []))
            out.coverage.setdefault("systems", []).extend(cov.get("systems", []))
        if only and len(every) > 1:
            out.complete = False                      # other projects were not looked at: additive only, never tombstones
        out.coverage["origin"] = "static"
        out.stats["projects"] = len(revs)
        out.revision = revs[0][1] if len(revs) == 1 else ",".join(f"{p}@{rv[:12]}" for p, rv in revs)[:2000]
        return out

    async def _scan_project(self, api: str, path: str, system: str, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None,
                            limit: int) -> ScanResult:
        rr = await self._project(api, path, secret)
        rr.raise_for_status()
        proj = rr.json()
        pid = proj["id"]
        default = proj.get("default_branch") or "main"
        r = ScanResult()
        if cfg.get("analyze_code", True) and not proj.get("empty_repo"):
            code = await GitRepoConnector().scan({"url": proj["http_url_to_repo"], "name": system, "content": cfg.get("content") or "auto"},
                                                 {"token": secret.get("token", ""), "username": "oauth2"}, ref or default)
            r.observations, r.documents, r.revision = code.observations, code.documents, code.revision
            r.coverage, r.stats, r.warnings, r.complete = code.coverage, dict(code.stats), list(code.warnings), code.complete
        else:
            head = await self._get(f"{api}/projects/{pid}/repository/commits/{quote(ref or default, safe='')}", secret)
            r.revision = head.json().get("id", "") if head.status_code == 200 else ""
        sk = f"system:{system}"
        r.node("static", sk, "software-system", system, V, ref=proj.get("web_url", ""),
               attrs={"gitlab": path, "gitlab_id": pid, "description": proj.get("description") or "", "default_branch": default,
                      "visibility": proj.get("visibility"), "topics": proj.get("topics") or proj.get("tag_list") or [],
                      "archived": proj.get("archived", False), "last_activity_at": proj.get("last_activity_at"),
                      "web_url": proj.get("web_url")})
        branches = await self._paged(f"{api}/projects/{pid}/repository/branches", secret, {}, 300)
        wanted = set(cfg.get("branches") or []) | {default}
        r.stats["branches"] = len(branches)
        r.node("static", f"{sk}#branches", "document", f"{system} branches", V, ref=f"{proj.get('web_url', '')}/-/branches",
               attrs={"branches": [{"name": b["name"], "sha": (b.get("commit") or {}).get("id"), "protected": b.get("protected", False),
                                    "committed_at": (b.get("commit") or {}).get("committed_date")}
                                   for b in branches if b["name"] in wanted][:50], "total": len(branches)})
        if cfg.get("issues", True) and proj.get("issues_enabled", True):
            issues = await self._paged(f"{api}/projects/{pid}/issues", secret, {"scope": "all", "order_by": "updated_at", "sort": "desc"}, limit)
            for i in issues:
                self.work_item(r, path, system, i, "issue")
            r.stats["issues"] = len(issues)
        if cfg.get("merge_requests", True) and proj.get("merge_requests_enabled", True):
            mrs = await self._paged(f"{api}/projects/{pid}/merge_requests", secret,
                                    {"scope": "all", "state": "all", "order_by": "updated_at", "sort": "desc"}, limit)
            for m in mrs:
                self.work_item(r, path, system, m, "merge_request")
            r.stats["merge_requests"] = len(mrs)
        r.coverage.setdefault("prefixes", []).extend([f"work-item:gitlab/{path}#", f"work-item:gitlab/{path}!"])
        return r

    @staticmethod
    def work_item(r: ScanResult, path: str, system: str, i: dict[str, Any], typ: str) -> str:
        """Issue / merge request from the REST API or a webhook `object_attributes` (+ top-level labels/assignees)."""
        iid = int(i["iid"])
        wk = _wid(path, iid, typ)
        state = {"opened": "open"}.get(str(i.get("state")), i.get("state"))
        labels = [lb if isinstance(lb, str) else lb.get("title") or lb.get("name") for lb in i.get("labels") or []]
        assignees = [a.get("username") for a in i.get("assignees") or [] if isinstance(a, dict)]
        author = (i.get("author") or {}).get("username") if isinstance(i.get("author"), dict) else i.get("author_username")
        url = i.get("web_url") or i.get("url")
        attrs = {"provider": "gitlab", "type": typ, "number": iid, "state": state, "url": url, "labels": [x for x in labels if x],
                 "assignees": [x for x in assignees if x], "author": author, "created_at": i.get("created_at"),
                 "updated_at": i.get("updated_at"), "closed_at": i.get("closed_at")}
        if typ == "merge_request":
            attrs.update({"merged_at": i.get("merged_at"), "draft": bool(i.get("draft") or i.get("work_in_progress")),
                          "head": {"ref": i.get("source_branch"), "sha": i.get("sha") or (i.get("last_commit") or {}).get("id")},
                          "base": i.get("target_branch"), "merge_commit_sha": i.get("merge_commit_sha") or i.get("squash_commit_sha")})
        prefix = "!" if typ == "merge_request" else "#"
        r.node("issue", wk, "work-item", f"{prefix}{iid} {i.get('title', '')}"[:400], V, attrs=attrs, ref=url or "")
        r.edge("issue", wk, "references", f"system:{system}", V, ref=url or "")
        if typ == "merge_request":
            for n in sorted({int(x) for x in CLOSES_RX.findall(f"{i.get('title', '')}\n{i.get('description') or ''}")}):
                r.edge("issue", wk, "implements", _wid(path, n, "issue"), V, attrs={"detected_by": "closing keyword"}, ref=url or "")
        return wk

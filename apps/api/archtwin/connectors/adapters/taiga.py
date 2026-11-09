"""Taiga connector (read-only — AT-WORK_CONNECTORS-001..003; phase-02 task 6.2). Self-hosted Taiga or taiga.io.

One Taiga project per connector: epics, user stories, tasks, issues and sprints (milestones) become `work-item` nodes
(origin `issue`) with provider ids, URLs, status, assignment, timestamps and provenance; a task `implements` its user story,
a user story `implements` its epics and `references` its sprint. Webhooks (X-TAIGA-WEBHOOK-SIGNATURE, HMAC-SHA1) update
single items; a scheduled/manual scan reconciles (and is the only thing that tombstones — partial never does).

Authentication: anonymous (public projects), an application/bearer token, or username + password exchanged at
`POST /api/v1/auth` for a session token (the only non-GET call, through `egress.guarded_login`). No write call exists.
Taiga's `X-Pagination-Next` links can be plain `http://` behind a TLS proxy, so pages are requested by number instead.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from archtwin.common.egress import EgressDenied, check_url, guarded_get, guarded_login, tls_verify
from archtwin.connectors.sdk import ScanResult, TestResult

V = "taiga-rest/1.0"
SLUG_RX = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,99}$")
MAX_PAGES = 40
KINDS = {"epic": "epics", "userstory": "userstories", "task": "tasks", "issue": "issues"}
URL_PART = {"epic": "epic", "userstory": "us", "task": "task", "issue": "issue"}


class AuthFailed(Exception):
    pass


def parse_target(cfg: dict[str, Any], *, check: bool = True) -> tuple[str, str, str]:
    """-> (web base, api base, project slug). Accepts the project URL the user sees, e.g.
    https://taiga.example.com/project/my-proj/kanban, or url + project."""
    raw = str(cfg.get("url") or "").strip()
    if not raw:
        raise ValueError("url is required (the Taiga project URL, e.g. https://taiga.example.com/project/<slug>/kanban)")
    u = urlsplit(raw)
    if u.scheme not in ("https", "http") or not u.netloc:
        raise ValueError("url must be an http(s) URL")
    web = f"{u.scheme}://{u.netloc}"
    m = re.search(r"/project/([^/]+)", u.path)
    slug = str(cfg.get("project") or (m.group(1) if m else "")).strip().lower()
    if not SLUG_RX.match(slug):
        raise ValueError("project slug missing or invalid: paste the project URL (…/project/<slug>/…) or set project")
    api = str(cfg.get("api_url") or f"{web}/api/v1").rstrip("/")
    if check:                      # webhook ingress only reads the slug: no outbound call, no DNS
        check_url(api)
    return web, api, slug


def _wk(slug: str, ref: int | str) -> str:
    return f"work-item:taiga/{slug}#{ref}"


def _name(v: Any, key: str = "name") -> Any:
    return v.get(key) if isinstance(v, dict) else None


class TaigaConnector:
    kind = "taiga"
    flag = "connector.taiga"
    manifest = {"name": "Taiga", "category": "work", "origin": "issue",
                "scopes": ["projects:read", "userstories:read", "tasks:read", "issues:read", "epics:read", "milestones:read"],
                "freshness_sla_s": 86400, "webhooks": ["userstory", "task", "issue", "epic", "milestone"],
                "config": {"url": "https://taiga.example.com/project/<slug>/kanban", "project": "slug (optional when in url)",
                           "system": "optional software system the work belongs to", "epics": True, "user_stories": True,
                           "tasks": True, "issues": True, "sprints": True, "max_items": 2000},
                "secret": {"username": "Taiga user (read access to the project)", "password": "its password",
                           "token": "or an application/bearer token instead of username + password",
                           "webhook_secret": "optional — the webhook key (X-TAIGA-WEBHOOK-SIGNATURE)"}}

    async def _headers(self, api: str, secret: dict[str, Any]) -> dict[str, str]:
        h = {"Accept": "application/json", "User-Agent": "archtwin-connector", "Accept-Language": "en"}
        if secret.get("token"):
            h["Authorization"] = f"Bearer {secret['token']}"
        elif secret.get("username") and secret.get("password"):
            r = await guarded_login(f"{api}/auth", json={"type": "normal", "username": str(secret["username"]),
                                                          "password": str(secret["password"])}, headers=h)
            if r.status_code != 200 or not (r.json() or {}).get("auth_token"):
                raise AuthFailed(f"Taiga login failed (HTTP {r.status_code})")
            h["Authorization"] = f"Bearer {r.json()['auth_token']}"
        return h

    @staticmethod
    async def _paged(url: str, h: dict[str, str], params: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            r = await guarded_get(url, headers=h, params={**params, "page": page}, timeout=30)
            if r.status_code == 404 and page > 1:            # past the last page
                break
            r.raise_for_status()
            batch = r.json()
            out.extend(batch)
            total = r.headers.get("x-pagination-count", "")
            if (not batch or r.headers.get("x-paginated", "").lower() != "true" or not r.headers.get("x-pagination-next")
                    or (total.isdigit() and len(out) >= int(total)) or len(out) >= limit):
                break
        return out[:limit]

    async def test(self, cfg: dict[str, Any], secret: dict[str, Any]) -> TestResult:
        try:
            web, api, slug = parse_target(cfg)
            warnings = [] if tls_verify(api) else [f"TLS certificate of {urlsplit(api).hostname} is NOT verified (operator allow-list)"]
            if not (secret.get("token") or (secret.get("username") and secret.get("password"))):
                warnings.append("no credentials: only public projects are visible")
            h = await self._headers(api, secret)
            r = await guarded_get(f"{api}/projects/by_slug", headers=h, params={"slug": slug}, timeout=20)
            if r.status_code != 200:
                return TestResult(ok=False, warnings=[*warnings, f"project {slug!r} not accessible (HTTP {r.status_code})"])
            p = r.json()
            perms = list(p.get("my_permissions") or [])
            writes = sorted(x for x in perms if x.startswith(("add_", "modify_", "delete_", "admin_", "remove_")))
            if writes:
                warnings.append(f"credentials can change this project ({len(writes)} write permissions, e.g. {', '.join(writes[:3])}) — "
                                "a read-only member/observer is enough; ArchTwin never writes")
            return TestResult(ok=True, scopes=self.manifest["scopes"], warnings=warnings,
                              details={"project": {"id": p.get("id"), "name": p.get("name"), "slug": p.get("slug"),
                                                   "is_private": p.get("is_private"), "url": f"{web}/project/{slug}"},
                                       "authenticated": "Authorization" in h})
        except (EgressDenied, ValueError, AuthFailed) as e:
            return TestResult(ok=False, warnings=[str(e)])
        except Exception as e:  # noqa: BLE001
            return TestResult(ok=False, warnings=[f"{type(e).__name__}: {str(getattr(e, 'detail', e))[:200]}"])

    async def scan(self, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None) -> ScanResult:
        web, api, slug = parse_target(cfg)
        limit = min(int(cfg.get("max_items") or 2000), 10000)
        h = await self._headers(api, secret)
        pr = await guarded_get(f"{api}/projects/by_slug", headers=h, params={"slug": slug}, timeout=20)
        pr.raise_for_status()
        p = pr.json()
        pid, system = p["id"], cfg.get("system")
        r = ScanResult(revision=f"taiga:{slug}@{p.get('modified_date', '')}")
        pk = f"taiga:{slug}"
        r.node("issue", pk, "document", f"Taiga · {p.get('name', slug)}", V, ref=f"{web}/project/{slug}",
               attrs={"provider": "taiga", "project_id": pid, "slug": slug, "description": p.get("description") or "",
                      "is_private": p.get("is_private"), "modified_date": p.get("modified_date")})
        latest = str(p.get("modified_date") or "")
        enabled = {"epic": cfg.get("epics", True), "userstory": cfg.get("user_stories", True), "task": cfg.get("tasks", True),
                   "issue": cfg.get("issues", True)}
        for typ, endpoint in KINDS.items():
            if not enabled[typ]:
                continue
            items = await self._paged(f"{api}/{endpoint}", h, {"project": pid}, limit)
            for i in items:
                self.work_item(r, web, slug, i, typ, system)
                latest = max(latest, str(i.get("modified_date") or ""))
            r.stats[endpoint] = len(items)
            if len(items) >= limit:
                r.complete = False
                r.warnings.append(f"{endpoint}: max_items ({limit}) reached — partial scan, unseen items kept (not tombstoned)")
        if cfg.get("sprints", True):
            sprints = await self._paged(f"{api}/milestones", h, {"project": pid}, 500)
            for s in sprints:
                self.sprint(r, web, slug, s)
            r.stats["sprints"] = len(sprints)
        r.revision = f"taiga:{slug}@{latest}"
        r.coverage = {"origin": "issue", "prefixes": [f"work-item:taiga/{slug}#", f"work-item:taiga/{slug}/sprint/"], "systems": []}
        return r

    @staticmethod
    def sprint(r: ScanResult, web: str, slug: str, s: dict[str, Any]) -> str:
        sk = f"work-item:taiga/{slug}/sprint/{s.get('slug') or s.get('id')}"
        r.node("issue", sk, "work-item", f"Sprint {s.get('name', '')}"[:400], V, ref=f"{web}/project/{slug}/taskboard/{s.get('slug', '')}",
               attrs={"provider": "taiga", "type": "sprint", "id": s.get("id"), "closed": s.get("closed"),
                      "estimated_start": s.get("estimated_start"), "estimated_finish": s.get("estimated_finish"),
                      "created_at": s.get("created_date"), "updated_at": s.get("modified_date")})
        return sk

    @staticmethod
    def work_item(r: ScanResult, web: str, slug: str, i: dict[str, Any], typ: str, system: str | None = None) -> str:
        """Normalizes both the REST shape (`status_extra_info`, `assigned_to_extra_info`, …) and the webhook shape
        (`status`/`assigned_to`/`milestone`/`user_story` as nested objects)."""
        ref = i["ref"]
        wk = _wk(slug, ref)
        st = i.get("status_extra_info") or (i.get("status") if isinstance(i.get("status"), dict) else {}) or {}
        closed = bool(i.get("is_closed") if i.get("is_closed") is not None else st.get("is_closed"))
        assignee = _name(i.get("assigned_to_extra_info"), "username") or _name(i.get("assigned_to"), "username")
        owner = _name(i.get("owner_extra_info"), "username") or _name(i.get("owner"), "username")
        sprint_slug = i.get("milestone_slug") or _name(i.get("milestone"), "slug")
        url = i.get("permalink") or f"{web}/project/{slug}/{URL_PART[typ]}/{ref}"
        attrs = {"provider": "taiga", "type": {"userstory": "user_story"}.get(typ, typ), "number": ref, "id": i.get("id"),
                 "state": "closed" if closed else "open", "status": st.get("name"), "url": url,
                 "labels": [t[0] if isinstance(t, list) else t for t in i.get("tags") or [] if t],
                 "assignees": [assignee] if assignee else [], "author": owner,
                 "sprint": i.get("milestone_name") or _name(i.get("milestone")), "blocked": bool(i.get("is_blocked")),
                 "created_at": i.get("created_date"), "updated_at": i.get("modified_date"),
                 "closed_at": i.get("finish_date") or i.get("finished_date")}
        if typ == "userstory":
            attrs["points"] = i.get("total_points")
        r.node("issue", wk, "work-item", f"#{ref} {i.get('subject', '')}"[:400], V, attrs=attrs, ref=url)
        if typ == "task":
            parent = i.get("user_story_extra_info") or (i.get("user_story") if isinstance(i.get("user_story"), dict) else None)
            if parent and parent.get("ref") is not None:
                r.edge("issue", wk, "implements", _wk(slug, parent["ref"]), V, ref=url)
        if typ == "userstory":
            for e in i.get("epics") or []:
                if isinstance(e, dict) and e.get("ref") is not None:
                    r.edge("issue", wk, "implements", _wk(slug, e["ref"]), V, ref=url)
        if sprint_slug:
            r.edge("issue", wk, "references", f"work-item:taiga/{slug}/sprint/{sprint_slug}", V, ref=url)
        if system:
            r.edge("issue", wk, "references", f"system:{system}", V, ref=url)
        return wk

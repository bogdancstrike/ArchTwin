"""Webhook ingress (phase-02 task 1.5; AT-SOURCE_CODE_DISCOVERY-003, AT-WORK_CONNECTORS-001).

POST /api/v1/webhooks/{org_id}/{project_id}/{connector_id} — no user token; authenticity comes from the provider signature
verified against the connector's sealed `webhook_secret`:
  * GitHub:  X-Hub-Signature-256 = sha256=HMAC(secret, body); delivery id X-GitHub-Delivery
  * GitLab:  X-Gitlab-Token = the secret token (constant-time compare); delivery id X-Gitlab-Event-UUID / Idempotency-Key
  * Taiga:   X-TAIGA-WEBHOOK-SIGNATURE = hex HMAC-SHA1(secret, body); no delivery header, so the id is sha256(body)
  * generic: X-ArchTwin-Signature = sha256=HMAC(secret, f"{timestamp}.{body}"), X-ArchTwin-Timestamp within REPLAY_WINDOW_S,
             delivery id X-ArchTwin-Delivery
Rules:
  * wrong/missing signature, stale timestamp, unknown connector or flag off -> rejected, NOTHING stored, attempt metered
    (in-process counter + structured log; exported by /metrics when Prometheus lands)
  * each delivery id is processed once (unique (connector_id, delivery_id)); a duplicate returns 200 {"duplicate": true}
  * a push for a tracked branch queues ONE incremental scan per commit SHA (a second push of the same SHA is a no-op)
  * issue / pull-request events update that single work item from the payload (partial scan: never tombstones)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from archtwin.audit import service as audit
from archtwin.common.db import RequestContext, row, uow
from archtwin.common.ids import new_id
from archtwin.common.logging import log
from archtwin.common.schema import connectors, scan_runs, webhook_deliveries
from archtwin.connectors import registry
from archtwin.connectors import service as csvc
from archtwin.connectors.sdk import ScanResult
from archtwin.flags import service as flags

REPLAY_WINDOW_S = 300
MAX_BODY = 2_000_000
METRICS: Counter[str] = Counter()        # webhook_{accepted,duplicate,rejected_<reason>}


class Rejected(Exception):
    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status, self.reason = status, reason


def _hmac(secret: str, msg: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify(kind: str, secret: str, headers: dict[str, str], body: bytes, now: float | None = None) -> str:
    """Return the delivery id if the signature is valid, else raise Rejected. Constant-time comparison."""
    if not secret:
        raise Rejected(404, "webhooks_not_configured")
    if kind == "github":
        sig = headers.get("x-hub-signature-256", "")
        if not sig or not hmac.compare_digest(sig, _hmac(secret, body)):
            raise Rejected(401, "bad_signature")
        did = headers.get("x-github-delivery", "")
    elif kind == "gitlab":
        tok = headers.get("x-gitlab-token", "")
        if not tok or not hmac.compare_digest(tok.encode(), secret.encode()):
            raise Rejected(401, "bad_signature")
        did = headers.get("x-gitlab-event-uuid") or headers.get("idempotency-key") or headers.get("x-gitlab-webhook-uuid", "")
    elif kind == "taiga":
        sig = headers.get("x-taiga-webhook-signature", "")
        if not sig or not hmac.compare_digest(sig, hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()):
            raise Rejected(401, "bad_signature")
        did = "taiga-" + hashlib.sha256(body).hexdigest()[:40]
    else:
        ts = headers.get("x-archtwin-timestamp", "")
        if not ts.isdigit() or abs((now or time.time()) - int(ts)) > REPLAY_WINDOW_S:
            raise Rejected(401, "stale_or_missing_timestamp")
        sig = headers.get("x-archtwin-signature", "")
        if not sig or not hmac.compare_digest(sig, _hmac(secret, ts.encode() + b"." + body)):
            raise Rejected(401, "bad_signature")
        did = headers.get("x-archtwin-delivery", "")
    if not did or len(did) > 200:
        raise Rejected(400, "missing_delivery_id")
    return did


def _reject(e: Rejected, connector_id: uuid.UUID) -> Rejected:
    METRICS[f"webhook_rejected_{e.reason}"] += 1
    log.warning("webhook_rejected", connector=str(connector_id), reason=e.reason)
    return e


async def receive(org_id: uuid.UUID, project_id: uuid.UUID, connector_id: uuid.UUID, headers: dict[str, str], body: bytes) -> dict[str, Any]:
    if len(body) > MAX_BODY:
        raise _reject(Rejected(413, "too_large"), connector_id)
    ctx = RequestContext(None, org_id, project_id, trace_id=f"webhook:{connector_id}", system=True)
    async with uow(ctx) as conn:
        c = row((await conn.execute(select(connectors).where(connectors.c.id == connector_id))).first())
    impl = registry.get(c["kind"]) if c else None
    if not c or not c["enabled"] or impl is None or "webhooks" not in impl.manifest:
        raise _reject(Rejected(404, "unknown_connector"), connector_id)
    for k in ("module.connector-platform", registry.MODULE_FLAG[c["kind"]], impl.flag, "connectors.webhooks"):
        if not await flags.enabled(k, org_id, project_id):
            raise _reject(Rejected(404, f"flag_off:{k}"), connector_id)
    async with uow(ctx) as conn:
        secret = await csvc._unseal(conn, ctx, c["secret_id"])
    try:
        delivery = verify(c["kind"], str(secret.get("webhook_secret") or ""), headers, body)
    except Rejected as e:
        raise _reject(e, connector_id) from None
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        raise _reject(Rejected(400, "invalid_json"), connector_id) from None
    event = _event(c["kind"], headers, payload)

    # dedupe: claim the delivery id first (unique constraint); a redelivery is acknowledged and ignored
    did = new_id()
    async with uow(ctx) as conn:
        res = await conn.execute(pg_insert(webhook_deliveries).values(
            id=did, org_id=org_id, project_id=project_id, connector_id=connector_id, delivery_id=delivery, event=event,
            outcome="received").on_conflict_do_nothing(index_elements=["connector_id", "delivery_id"]).returning(webhook_deliveries.c.id))
        if res.first() is None:
            METRICS["webhook_duplicate"] += 1
            return {"duplicate": True, "delivery": delivery}
    outcome, scan_id, summary = await _handle(ctx, c, event, payload)
    async with uow(ctx) as conn:
        await conn.execute(webhook_deliveries.update().where(webhook_deliveries.c.id == did).values(
            outcome=outcome, scan_id=scan_id, summary=summary))
        await audit.record(conn, ctx, "connector.webhook", "connector", connector_id,
                           details={"event": event, "delivery": delivery, "outcome": outcome, **summary})
    METRICS["webhook_accepted"] += 1
    return {"duplicate": False, "delivery": delivery, "outcome": outcome, "scan_id": str(scan_id) if scan_id else None, **summary}


GITLAB_EVENTS = {"Push Hook": "push", "Merge Request Hook": "merge_request", "Issue Hook": "issue", "Confidential Issue Hook": "issue"}


def _event(kind: str, headers: dict[str, str], payload: dict[str, Any]) -> str:
    if kind == "gitlab":
        return GITLAB_EVENTS.get(headers.get("x-gitlab-event", ""), headers.get("x-gitlab-event", "unknown") or "unknown")
    if kind == "taiga":
        return f"taiga.{payload.get('type', 'unknown')}" if payload.get("type") != "test" else "ping"
    return headers.get("x-github-event") or headers.get("x-archtwin-event") or "push"


def _tracked_branches(c: dict[str, Any], payload: dict[str, Any]) -> set[str]:
    cfg = c["config"] or {}
    default = ((payload.get("repository") or {}).get("default_branch")) or ((payload.get("project") or {}).get("default_branch")) \
        or cfg.get("ref") or "main"
    return set(cfg.get("branches") or []) | {default}


async def _webhook_scan(ctx: RequestContext, c: dict[str, Any], event: str, ref: str, r: ScanResult) -> uuid.UUID:
    """Persist a single-item update as a partial scan (additive: never tombstones)."""
    sid = new_id()
    async with uow(ctx) as conn:
        await conn.execute(scan_runs.insert().values(id=sid, org_id=ctx.org_id, project_id=ctx.project_id, connector_id=c["id"],
                                                     mode="webhook", ref=ref[:200], status="running", started_at=datetime.now(UTC)))
    await csvc.persist(ctx, c, sid, r)
    return sid


async def _handle_gitlab_item(ctx: RequestContext, c: dict[str, Any], event: str, payload: dict[str, Any]) -> tuple[str, uuid.UUID | None, dict]:
    from archtwin.connectors.adapters.gitlab import GitLabConnector, split_project
    cfg = c["config"] or {}
    path = (payload.get("project") or {}).get("path_with_namespace", "")
    configured = {split_project(str(e), cfg.get("url"))[1] for e in cfg.get("projects") or []}
    in_group = any(path.startswith(split_project(str(g), cfg.get("url"))[1] + "/") for g in cfg.get("groups") or [])
    item = dict(payload.get("object_attributes") or {})
    if not item or not path or (path not in configured and not in_group):
        return "ignored_unknown_repo", None, {"repo": path}
    item.setdefault("labels", payload.get("labels") or [])
    item.setdefault("assignees", payload.get("assignees") or [])
    item.setdefault("author_username", (payload.get("user") or {}).get("username"))
    names = cfg.get("system_names") or {}
    system = names.get(path) or path.rsplit("/", 1)[-1]
    r = ScanResult(revision=f"webhook:{event}:{item.get('updated_at', '')}", complete=False)
    GitLabConnector.work_item(r, path, system, item, "merge_request" if event == "merge_request" else "issue")
    sid = await _webhook_scan(ctx, c, event, f"{event}{'!' if event == 'merge_request' else '#'}{item.get('iid')}", r)
    return "work_item_updated", sid, {"item": f"{path}#{item.get('iid')}", "action": item.get("action", "")}


async def _handle_taiga(ctx: RequestContext, c: dict[str, Any], event: str, payload: dict[str, Any]) -> tuple[str, uuid.UUID | None, dict]:
    from archtwin.connectors.adapters.taiga import KINDS, TaigaConnector, parse_target
    web, _, slug = parse_target(c["config"] or {})
    typ = event.removeprefix("taiga.")
    data = payload.get("data") or {}
    permalink = str((data.get("project") or {}).get("permalink") or data.get("permalink") or "")
    if f"/project/{slug}/" not in permalink + "/":
        return "ignored_unknown_project", None, {"project": permalink[:200]}
    if payload.get("action") == "delete":       # tombstoning is left to the next complete reconcile scan
        return "ignored_delete_until_reconcile", None, {"type": typ, "ref": data.get("ref")}
    r = ScanResult(revision=f"webhook:{typ}:{data.get('modified_date', payload.get('date', ''))}", complete=False)
    if typ == "milestone":
        TaigaConnector.sprint(r, web, slug, data)
    elif typ in KINDS and data.get("ref") is not None:
        TaigaConnector.work_item(r, web, slug, data, typ, (c["config"] or {}).get("system"))
    else:
        return "ignored_event", None, {"event": event}
    sid = await _webhook_scan(ctx, c, event, f"{typ}#{data.get('ref', data.get('slug', ''))}", r)
    return "work_item_updated", sid, {"item": f"{slug}#{data.get('ref', data.get('slug'))}", "action": payload.get("action", "")}


async def _handle(ctx: RequestContext, c: dict[str, Any], event: str, payload: dict[str, Any]) -> tuple[str, uuid.UUID | None, dict]:
    if event == "ping":
        return "pong", None, {}
    if c["kind"] == "taiga":
        return await _handle_taiga(ctx, c, event, payload)
    if event == "push":
        ref = str(payload.get("ref", ""))
        sha = str(payload.get("after") or payload.get("sha") or "")
        branch = ref.removeprefix("refs/heads/")
        if not ref.startswith("refs/heads/") or branch not in _tracked_branches(c, payload):
            return "ignored_untracked_ref", None, {"ref": ref}
        if not sha or set(sha) == {"0"}:
            return "ignored_branch_deleted", None, {"ref": ref}
        scan_ref = sha
        if c["kind"] == "gitlab":                  # a GitLab connector may watch several projects: scan only the pushed one
            path = (payload.get("project") or {}).get("path_with_namespace", "")
            if not path:
                return "ignored_unknown_repo", None, {"repo": path}
            scan_ref = f"{path}@{sha}"
        async with uow(ctx) as conn:      # one extraction per commit, even across distinct deliveries of the same push
            existing = (await conn.execute(select(scan_runs.c.id).where(and_(
                scan_runs.c.connector_id == c["id"], scan_runs.c.ref == scan_ref,
                scan_runs.c.status.in_(("queued", "running", "complete", "partial"))
            )).limit(1))).first()
        if existing:
            return "duplicate_commit", existing.id, {"ref": ref, "sha": sha}
        s = await csvc.request_scan(ctx, c["id"], scan_ref)
        return "scan_queued", s["id"], {"ref": ref, "sha": sha, "commits": len(payload.get("commits") or [])}
    if c["kind"] == "gitlab" and event in ("issue", "merge_request"):
        return await _handle_gitlab_item(ctx, c, event, payload)
    if c["kind"] == "github" and event in ("issues", "pull_request"):
        item = payload.get("issue") or payload.get("pull_request")
        repo = (payload.get("repository") or {}).get("full_name", "")
        if not item or not repo or repo not in (c["config"] or {}).get("repos", []):
            return "ignored_unknown_repo", None, {"repo": repo}
        from archtwin.connectors.adapters.github import GitHubConnector
        names = (c["config"] or {}).get("system_names") or {}
        system = names.get(repo) or repo.split("/")[1]
        r = ScanResult(revision=f"webhook:{event}:{item.get('updated_at', '')}", complete=False)
        GitHubConnector._work_item(r, repo, system, item, "pull_request" if event == "pull_request" else "issue")
        sid = new_id()
        async with uow(ctx) as conn:
            await conn.execute(scan_runs.insert().values(id=sid, org_id=ctx.org_id, project_id=ctx.project_id, connector_id=c["id"],
                                                         mode="webhook", ref=f"{event}#{item.get('number')}", status="running",
                                                         started_at=datetime.now(UTC)))
        await csvc.persist(ctx, c, sid, r)
        return "work_item_updated", sid, {"item": f"{repo}#{item.get('number')}", "action": payload.get("action", "")}
    return "ignored_event", None, {"event": event}

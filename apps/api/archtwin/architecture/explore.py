"""Exploring the architecture: search any element and see everything linked to it (Architecture tab search + side panel).

Pure functions over a snapshot graph, plus a mentions lookup through the documents module's service interface.
"""
from __future__ import annotations

from typing import Any

from archtwin.common.db import RequestContext, uow
from archtwin.common.errors import not_found
from archtwin.diagrams import views
from archtwin.documents import service as docs

HIDDEN_KINDS = {"library"}


def search(g: dict[str, Any], q: str, limit: int = 30) -> list[dict[str, Any]]:
    """Rank by exact name > prefix > substring (name or key); each hit says which view draws it and what it zooms into."""
    ql = q.lower().strip()
    hits = []
    for k, n in g["nodes"].items():
        if n["kind"] in HIDDEN_KINDS:
            continue
        name = (n.get("name") or "").lower()
        score = 3 if name == ql else 2 if name.startswith(ql) else 1 if ql in name or ql in k.lower() else 0
        if score:
            hits.append((-score, len(name), k, n))
    hits.sort(key=lambda h: h[:3])
    return [{"key": k, "name": n.get("name", k), "kind": n["kind"], "technology": n["attributes"].get("technology") or n["attributes"].get("element") or "",
             "path": n["attributes"].get("path", ""), "parent_view": views.parent_view(g, k), "zoom": views.zoom_target(g, k)}
            for _, _, k, n in hits[:limit]]


def linked(g: dict[str, Any], key: str) -> dict[str, list[dict[str, Any]]]:
    """ADRs and work items that reference the element, and relations drawn in documentation diagrams."""
    out: dict[str, list[dict[str, Any]]] = {"adrs": [], "work_items": [], "documented": []}
    for e in g["edges"].values():
        src = g["nodes"].get(e["source"], {})
        if e["target"] == key and e["kind"] == "references" and src.get("kind") in ("adr", "work-item"):
            a = src["attributes"]
            out["adrs" if src["kind"] == "adr" else "work_items"].append(
                {"key": e["source"], "name": src.get("name"), "state": a.get("state"), "status": a.get("status"), "url": a.get("url") or "",
                 "provider": a.get("provider", "")})
        if e["attributes"].get("documented") and key in (e["source"], e["target"]):
            other = e["target"] if e["source"] == key else e["source"]
            out["documented"].append({"edge": e["key"], "kind": e["kind"], "other": g["nodes"].get(other, {}).get("name", other),
                                      "diagram": e["attributes"].get("diagram"), "direction": "out" if e["source"] == key else "in"})
    return out


async def mentions(ctx: RequestContext, name: str, per_kind: int = 5) -> list[dict[str, Any]]:
    if len(name) < 3:
        return []
    out = []
    async with uow(ctx) as conn:
        for kind in ("docs", "code"):
            for p in await docs.search_passages(conn, ctx, name, limit=per_kind, kind=kind):
                out.append({"kind": kind, "path": p["path"], "title": p["title"], "heading": p["heading"], "line_start": p["line_start"],
                            "snippet": p["text"][:240]})
    return out


SOURCE_CONTEXT = 30


def source_span(n: dict[str, Any]) -> tuple[str, int, int] | None:
    """Where an element's source lives: a code element's own lines, an endpoint's handler, a table's declaration."""
    a = n["attributes"]
    if n["kind"] == "code" and a.get("path"):
        return a["path"], int(a.get("line_start") or 1), int(a.get("line_end") or a.get("line_start") or 1)
    ev = (n.get("evidence") or [{}])[0].get("span") or {}
    if n["kind"] in ("api-endpoint", "table") and ev.get("path") and ev.get("line_start"):
        s0 = int(ev["line_start"])
        return ev["path"], max(1, s0 - 2), s0 + SOURCE_CONTEXT
    return None


async def source(ctx: RequestContext, n: dict[str, Any]) -> dict[str, Any] | None:
    span = source_span(n)
    if not span:
        return None
    async with uow(ctx) as conn:
        return await docs.source_lines(conn, ctx, *span)


async def detail(ctx: RequestContext, g: dict[str, Any], key: str) -> dict[str, Any]:
    n = g["nodes"].get(key)
    if not n:
        raise not_found("element")
    name = n.get("name") or key.rsplit("/", 1)[-1]
    return {"key": key, "name": name, "kind": n["kind"], "attributes": dict(n["attributes"]), "origins": n["origins"],
            "confidence": n["confidence"], "linked": linked(g, key), "mentions": await mentions(ctx, name), "source": await source(ctx, n)}

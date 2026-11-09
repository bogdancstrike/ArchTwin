"""Export service: collect a resource as Markdown items (the pages' data), then render to md / docx / pdf / zip.

* collect(): one `Collection` per export — a combined Markdown document plus one item per element (flow, ADR, doc).
* render(): `FORMATS` renders the combined document; `zip` bundles every item as Markdown, the combined document in all
  three formats and a manifest.json with provenance (project, snapshot, generated_at, source revisions).
"""
from __future__ import annotations

import io
import json
import re
import tempfile
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from archtwin.architecture import flows as flow_rec
from archtwin.architecture import service as arch
from archtwin.common.db import RequestContext
from archtwin.common.errors import not_found, problem
from archtwin.decisions import service as decisions
from archtwin.documents import engine as docengine
from archtwin.drift import service as drift
from archtwin.exports import builders
from archtwin.exports.renderers import FORMATS
from archtwin.projects import service as projects

RESOURCES = ("architecture", "flows", "drift", "decisions", "docs")
ALL_FORMATS = (*FORMATS, "zip")
MAX_MARKDOWN = 8_000_000            # characters of combined Markdown
MAX_PDF_MARKDOWN = 3_000_000        # PDF rendering is the slowest: smaller cap
MAX_ITEMS = 2000


@dataclass
class Item:
    name: str
    title: str
    markdown: str


@dataclass
class Collection:
    resource: str
    project: dict[str, Any]
    title: str
    markdown: str
    items: list[Item] = field(default_factory=list)
    snapshot: dict[str, Any] | None = None

    def manifest(self) -> dict[str, Any]:
        snap = self.snapshot or {}
        inputs = (snap.get("inputs") or {}).get("scans", []) if isinstance(snap.get("inputs"), dict) else []
        return {"generator": "ArchTwin", "resource": self.resource, "title": self.title, "generated_at": datetime.now(UTC).isoformat(),
                "project": {"id": str(self.project["id"]), "slug": self.project.get("slug"), "title": self.project.get("title")},
                "snapshot": {"id": str(snap["id"]), "version": snap.get("version"), "created_at": str(snap.get("created_at"))} if snap else None,
                "source_revisions": [{"connector_id": str(s.get("connector_id", "")), "revision": s.get("revision"), "scan_id": str(s.get("scan_id", ""))}
                                     for s in inputs if isinstance(s, dict)],
                "items": [{"file": f"{i.name}.md", "title": i.title} for i in self.items]}


@dataclass
class Artifact:
    filename: str
    media_type: str
    body: bytes | None = None
    stream: Iterator[bytes] | None = None


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60] or "export"


async def collect(ctx: RequestContext, resource: str, item_id: str | None = None, filters: dict[str, str | None] | None = None) -> Collection:
    if resource not in RESOURCES:
        raise problem(422, "AT-EXPORT-001", "Unknown export", f"resource must be one of {', '.join(RESOURCES)}")
    p = await projects.get_project(ctx)
    title = p["title"]
    if resource == "architecture":
        g = await arch.graph(ctx)
        md = builders.architecture_md(g, title)
        return Collection(resource, p, f"{title} — Architecture model", md, [Item("architecture", "Architecture model", md)], g.get("snapshot"))
    if resource == "flows":
        g = await arch.graph(ctx)
        fl = flow_rec.recognize(g)["flows"]
        if item_id:
            fl = [f for f in fl if f["id"] == item_id]
            if not fl:
                raise not_found("flow")
            md = builders.flow_md(fl[0])
            return Collection(resource, p, fl[0]["name"], f"{md}\n{builders.provenance(title, g.get('snapshot'))}",
                              [Item(slug(fl[0]["name"]), fl[0]["name"], md)], g.get("snapshot"))
        fl = fl[:MAX_ITEMS]
        return Collection(resource, p, f"{title} — Flows", builders.flows_md(fl, title, g.get("snapshot")),
                          [Item(f"{i:04d}-{slug(f['name'])}", f["name"], builders.flow_md(f)) for i, f in enumerate(fl, 1)], g.get("snapshot"))
    if resource == "drift":
        f = filters or {}
        found = await drift.list_findings(ctx, f.get("status"), f.get("verdict"))
        if f.get("severity"):
            found = [x for x in found if x["severity"] == f["severity"]]
        if item_id:
            found = [x for x in found if str(x["id"]) == item_id]
        g = await arch.graph(ctx)
        md = builders.drift_md(found, title, g.get("snapshot"), f)
        return Collection(resource, p, f"{title} — Drift findings", md, [Item("drift-findings", "Drift findings", md)], g.get("snapshot"))
    if resource == "decisions":
        index = await decisions.list_(ctx)
        if item_id:
            index = [a for a in index if str(a["id"]) == item_id]
            if not index:
                raise not_found("ADR")
        full = [await decisions.get(ctx, a["id"]) for a in index[:MAX_ITEMS]]
        mds = [decisions.to_markdown(a) for a in full]
        items = [Item(f"ADR-{a['number']:04d}-{slug(a['title'])}", f"ADR-{a['number']:04d} {a['title']}", m) for a, m in zip(full, mds, strict=True)]
        if item_id:
            return Collection(resource, p, items[0].title, mds[0], items)
        return Collection(resource, p, f"{title} — Decision records", builders.decisions_md(mds, title, index), items)
    gen = await docengine.list_generated(ctx)
    latest: dict[str, dict[str, Any]] = {}
    for d in gen:                                         # ordered template, version desc: keep the newest of each type
        latest.setdefault(d["template"], d)
    chosen = [d for d in gen if str(d["id"]) == item_id] if item_id else list(latest.values())
    if item_id and not chosen:
        raise not_found("document")
    docs = [await docengine.get_generated(ctx, d["id"]) for d in chosen]
    items = [Item(f"{d['template']}-v{d['version']}", f"{d['template']} v{d['version']}", d["content"]) for d in docs]
    if item_id:
        return Collection(resource, p, items[0].title, docs[0]["content"], items)
    return Collection(resource, p, f"{title} — Documentation", builders.docs_md([(i.title, i.markdown) for i in items], title), items)


def _check_size(md: str, fmt: str) -> None:
    cap = MAX_PDF_MARKDOWN if fmt in ("pdf", "zip") else MAX_MARKDOWN
    if len(md) > cap:
        raise problem(413, "AT-EXPORT-002", "Export too large", f"{len(md):,} characters; narrow it (filters or a single item) or use Markdown.")


def render(col: Collection, fmt: str) -> Artifact:
    if fmt not in ALL_FORMATS:
        raise problem(422, "AT-EXPORT-003", "Unknown format", f"format must be one of {', '.join(ALL_FORMATS)}")
    _check_size(col.markdown, fmt)
    base = f"{slug(col.project.get('slug') or col.project['title'])}-{col.resource}-{datetime.now(UTC):%Y-%m-%d}"
    if fmt != "zip":
        f = FORMATS[fmt]
        return Artifact(f"{base}.{f.ext}", f.media_type, body=f.render(col.title, col.markdown))
    spool = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024)  # noqa: SIM115 — closed by the streaming generator
    with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(col.manifest(), indent=2, default=str))
        for f in FORMATS.values():
            z.writestr(f"{base}.{f.ext}", f.render(col.title, col.markdown))
        if len(col.items) > 1:
            for it in col.items:
                z.writestr(f"items/{it.name}.md", it.markdown)
    spool.seek(0)

    def chunks() -> Iterator[bytes]:
        try:
            while b := spool.read(256 * 1024):
                yield b
        finally:
            spool.close()
    return Artifact(f"{base}.zip", "application/zip", stream=chunks())


def zip_names(data: bytes) -> list[str]:
    return zipfile.ZipFile(io.BytesIO(data)).namelist()



"""Documents and passages with provenance (AT-DOCUMENT_PARSING). Markdown/text parsed natively; PDF/DOCX via docling-serve."""
from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

import httpx
from sqlalchemy import and_, func, select, text

from archtwin.common.db import RequestContext, row, rows
from archtwin.common.errors import problem
from archtwin.common.ids import new_id
from archtwin.common.schema import documents, passages
from archtwin.config import settings

PARSER_MD = "markdown-sections/1.0"
MAX_PASSAGE = 1800
MAGIC = {b"%PDF": "application/pdf", b"PK\x03\x04": "application/zip"}


def split_markdown(text: str) -> list[dict[str, Any]]:
    """Split on headings, then cap passage size; keep 1-based line ranges for provenance."""
    lines = text.splitlines()
    out, cur, heading, start = [], [], "", 1

    def flush(end: int):
        body = "\n".join(cur).strip()
        if body:
            for i in range(0, len(body), MAX_PASSAGE):
                out.append({"heading": heading[:300], "text": body[i:i + MAX_PASSAGE], "line_start": start, "line_end": end})

    in_code = False
    for i, ln in enumerate(lines, 1):
        if ln.strip().startswith("```"):
            in_code = not in_code
        m = re.match(r"^(#{1,4})\s+(.+)$", ln) if not in_code else None
        if m:
            flush(i - 1)
            cur, heading, start = [], m.group(2).strip(), i
        cur.append(ln)
    flush(len(lines))
    return out


async def upsert_document(conn, ctx: RequestContext, *, title: str, path: str, text_body: str, mime: str, source_kind: str,
                          connector_id: uuid.UUID | None, revision: str = "", tags: list[str] | None = None,
                          parser: str = PARSER_MD) -> tuple[uuid.UUID, bool]:
    sha = hashlib.sha256(text_body.encode()).hexdigest()
    latest = (await conn.execute(select(documents.c.id, documents.c.sha256, documents.c.version)
                                 .where(and_(documents.c.project_id == ctx.project_id, documents.c.path == path))
                                 .order_by(documents.c.version.desc()).limit(1))).first()
    if latest and latest.sha256 == sha:
        return latest.id, False
    did = new_id()
    await conn.execute(documents.insert().values(
        id=did, org_id=ctx.org_id, project_id=ctx.project_id, title=title[:300], source_kind=source_kind, connector_id=connector_id,
        path=path, mime=mime, sha256=sha, version=(latest.version + 1) if latest else 1, revision=revision,
        status="parsed", parser_version=parser + (";tags=" + ",".join(tags) if tags else ""), created_by=ctx.actor_id))
    chunks = split_markdown(text_body) if mime in ("text/markdown", "text/plain") else [{"heading": "", "text": text_body[:MAX_PASSAGE]}]
    for i, ch in enumerate(chunks):
        await conn.execute(passages.insert().values(id=new_id(), org_id=ctx.org_id, project_id=ctx.project_id, document_id=did,
                                                    ord=i, text=ch["text"], heading=ch.get("heading", ""), page=ch.get("page"),
                                                    line_start=ch.get("line_start"), line_end=ch.get("line_end")))
    return did, True


def sniff(data: bytes, filename: str) -> str:
    for magic, mime in MAGIC.items():
        if data.startswith(magic):
            if mime == "application/zip":
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if filename.lower().endswith(".docx") \
                    else "application/zip"
            return mime
    head = data[:8192]
    if b"\x00" in head or sum(b < 9 or 13 < b < 32 or b == 127 for b in head) > max(4, len(head) // 100):
        return "application/octet-stream"          # NUL/control bytes: binary regardless of extension
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return "application/octet-stream"
    return "text/markdown" if filename.lower().endswith((".md", ".markdown")) else "text/plain"


async def parse_upload(data: bytes, filename: str) -> tuple[str, str, str]:
    """Returns (mime, text, parser_version). Rejects unknown/binary types (magic bytes, not the extension)."""
    if len(data) > settings().max_upload_mb * 1024 * 1024:
        raise problem(413, "AT-DOC-001", "File too large")
    mime = sniff(data, filename)
    if mime in ("text/markdown", "text/plain"):
        return mime, data.decode("utf-8", "replace"), PARSER_MD
    if mime in ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        if not settings().docling_url:
            raise problem(422, "AT-DOC-002", "Parser unavailable",
                          "PDF/DOCX parsing needs the 'documents' profile (docling-serve). Markdown and text work without it.")
        async with httpx.AsyncClient(timeout=600) as c:
            r = await c.post(f"{settings().docling_url.rstrip('/')}/v1/convert/file", files={"files": (filename, data, mime)},
                             data={"to_formats": "md"})
            r.raise_for_status()
            md = (r.json().get("document") or {}).get("md_content") or ""
        return "text/markdown", md, "docling-serve/1"
    raise problem(415, "AT-DOC-003", "Unsupported file type", f"Detected {mime}; allowed: Markdown, text, PDF, DOCX.")


async def list_documents(conn, ctx: RequestContext, q: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    latest = select(documents.c.path, func.max(documents.c.version).label("v")).where(
        documents.c.project_id == ctx.project_id).group_by(documents.c.path).subquery()
    stmt = (select(documents.c.id, documents.c.title, documents.c.path, documents.c.mime, documents.c.version,
                   documents.c.source_kind, documents.c.revision, documents.c.parser_version, documents.c.created_at)
            .join(latest, and_(latest.c.path == documents.c.path, latest.c.v == documents.c.version))
            .order_by(documents.c.path).limit(limit))
    if q:
        stmt = stmt.where(documents.c.title.ilike(f"%{q}%") | documents.c.path.ilike(f"%{q}%"))
    return rows(await conn.execute(stmt))


async def get_document(conn, ctx: RequestContext, doc_id: uuid.UUID) -> dict[str, Any] | None:
    d = row((await conn.execute(select(documents).where(documents.c.id == doc_id))).first())
    if d:
        d["passages"] = rows(await conn.execute(select(passages.c.id, passages.c.ord, passages.c.heading, passages.c.text,
                                                       passages.c.line_start, passages.c.line_end)
                                                .where(passages.c.document_id == doc_id).order_by(passages.c.ord)))
    return d


async def search_passages(conn, ctx: RequestContext, query: str, limit: int = 8, *, connector_ids: list[str] | None = None,
                          uploads: bool = True) -> list[dict[str, Any]]:
    """Project-scoped FTS (RLS + explicit project filter); only the latest version of each document.
    `connector_ids` (None = every source) restricts to documents from those connectors; `uploads` adds uploaded files."""
    words = [w for w in re.findall(r"[A-Za-z0-9_]{3,}", query.lower())][:12]
    if not words:
        return []
    tsq = " | ".join(words)
    flt = ""
    params: dict[str, Any] = {"p": ctx.project_id, "q": tsq, "n": limit}
    if connector_ids is not None:
        flt = " AND (d.connector_id = ANY(CAST(:cids AS uuid[]))" + (" OR d.connector_id IS NULL)" if uploads else ")")
        params["cids"] = connector_ids
    rs = await conn.execute(text(f"""
        WITH latest AS (SELECT DISTINCT ON (path) id FROM documents WHERE project_id = :p ORDER BY path, version DESC)
        SELECT ps.id, ps.text, ps.heading, ps.line_start, ps.line_end, d.title, d.path, d.revision, d.id AS document_id,
               d.connector_id, ts_rank(ps.tsv, to_tsquery('english', :q)) AS rank
        FROM passages ps JOIN documents d ON d.id = ps.document_id JOIN latest l ON l.id = d.id
        WHERE ps.project_id = :p AND ps.tsv @@ to_tsquery('english', :q){flt}
        ORDER BY rank DESC LIMIT :n"""), params)
    return [dict(r._mapping) for r in rs]

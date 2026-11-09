"""Server-side pagination, search, filtering and sorting for every list in the UI (one contract, one envelope).

Query:  page (1-based), page_size in PAGE_SIZES (default 15), q (search text), sort (a column the endpoint allows), dir.
Result: {"items": [...], "total": n, "page": p, "page_size": s, "pages": ceil(n/s), "sort": ..., "dir": ...}
SQL lists use `paginate_select` (count + offset/limit in the database); computed lists (e.g. recognized flows) use
`paginate_items`. Endpoints keep their old array response when no paging parameter is sent (N-1 compatible clients).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from fastapi import Query
from sqlalchemy import ColumnElement, Select, func, or_, select

from archtwin.common.db import rows
from archtwin.common.errors import problem

PAGE_SIZES = (5, 15, 25, 50, 100)
DEFAULT_PAGE_SIZE = 15


@dataclass(frozen=True)
class PageQuery:
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    q: str = ""
    sort: str = ""
    dir: str = "desc"
    requested: bool = False          # the client asked for a page (otherwise legacy endpoints return a plain list)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def envelope(self, items: list[Any], total: int) -> dict[str, Any]:
        return {"items": items, "total": total, "page": self.page, "page_size": self.page_size,
                "pages": max(1, -(-total // self.page_size)), "sort": self.sort, "dir": self.dir}


def page_query(page: int | None = Query(None, ge=1), page_size: int | None = Query(None), q: str | None = Query(None, max_length=200),
               sort: str | None = Query(None, max_length=40), dir: str = Query("desc", pattern="^(asc|desc)$")) -> PageQuery:
    """FastAPI dependency."""
    size = page_size or DEFAULT_PAGE_SIZE
    if size not in PAGE_SIZES:
        raise problem(422, "AT-PAGE-001", "Invalid page size", ", ".join(map(str, PAGE_SIZES)))
    return PageQuery(page or 1, size, (q or "").strip(), sort or "", dir, requested=page is not None or page_size is not None)


async def paginate_select(conn, stmt: Select, pq: PageQuery, *, search: Sequence[ColumnElement] = (),
                          sorts: dict[str, ColumnElement] | None = None, default_sort: str = "") -> dict[str, Any]:
    """Count + order + offset/limit in SQL. Unknown sort keys fall back to `default_sort` (never raw user SQL)."""
    if pq.q and search:
        like = f"%{pq.q.lower()}%"
        stmt = stmt.where(or_(*[func.lower(c).like(like) for c in search]))
    total = (await conn.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar() or 0
    sorts = sorts or {}
    key = pq.sort if pq.sort in sorts else default_sort
    if key in sorts:
        col = sorts[key]
        stmt = stmt.order_by(None).order_by(col.desc().nulls_last() if pq.dir == "desc" else col.asc().nulls_last())
    items = rows(await conn.execute(stmt.offset(pq.offset).limit(pq.page_size)))
    return pq.envelope(items, total)


def paginate_items(items: Iterable[dict[str, Any]], pq: PageQuery, *, search: Callable[[dict[str, Any]], str] | None = None,
                   sorts: dict[str, Callable[[dict[str, Any]], Any]] | None = None, default_sort: str = "") -> dict[str, Any]:
    """The same contract for lists computed in memory."""
    data = list(items)
    if pq.q and search:
        ql = pq.q.lower()
        data = [x for x in data if ql in search(x).lower()]
    sorts = sorts or {}
    key = pq.sort if pq.sort in sorts else default_sort
    if key in sorts:
        data.sort(key=lambda x: (sorts[key](x) is None, sorts[key](x)), reverse=pq.dir == "desc")
    return pq.envelope(data[pq.offset: pq.offset + pq.page_size], len(data))

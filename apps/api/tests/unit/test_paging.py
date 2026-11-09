"""One pagination contract for every list: sizes 5/15/25/50/100 (default 15), search, sort, envelope."""
import pytest

from archtwin.common.paging import DEFAULT_PAGE_SIZE, PageQuery, page_query, paginate_items

ITEMS = [{"name": f"flow {i:02d}", "length": i % 7, "kind": "endpoint" if i % 2 else "data"} for i in range(1, 38)]


def test_defaults_and_validation():
    pq = page_query(page=None, page_size=None, q=None, sort=None, dir="desc")
    assert pq.page == 1 and pq.page_size == DEFAULT_PAGE_SIZE == 15 and not pq.requested
    assert page_query(page=2, page_size=None, q=" x ", sort="name", dir="asc").requested
    for bad in (10, 20, 1000):
        with pytest.raises(Exception, match="422"):
            page_query(page=1, page_size=bad, q=None, sort=None, dir="asc")


def test_envelope_search_sort_and_last_page():
    pq = PageQuery(page=3, page_size=15, requested=True)
    out = paginate_items(ITEMS, pq, sorts={"name": lambda x: x["name"]}, default_sort="name")
    assert out["total"] == 37 and out["pages"] == 3 and len(out["items"]) == 7                   # 15 + 15 + 7
    srt = paginate_items(ITEMS, PageQuery(page_size=5, sort="length", dir="desc", requested=True), sorts={"length": lambda x: x["length"]})
    assert [x["length"] for x in srt["items"]] == [6] * 5
    q = paginate_items(ITEMS, PageQuery(q="FLOW 1", page_size=25, requested=True), search=lambda x: x["name"])
    assert q["total"] == 10 and all(x["name"].startswith("flow 1") for x in q["items"])
    unknown = paginate_items(ITEMS, PageQuery(sort="drop table", page_size=5, requested=True), sorts={"name": lambda x: x["name"]}, default_sort="name")
    assert unknown["items"][0]["name"] == "flow 37"                                              # unknown sort -> safe default

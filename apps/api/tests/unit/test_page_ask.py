"""Ask a page: deterministic search ranks flows / decisions before any AI is involved."""
from archtwin.intelligence import page_ask as pa


def test_stemming_matches_word_families():
    assert pa.stem("dissemination") == pa.stem("disseminate") == pa.stem("disseminated")
    assert pa.terms("What is the flow of dissemination documents?") == [pa.stem("dissemination")]


def test_flow_ranking_prefers_name_and_endpoint_matches():
    def flow(name, parts, kind="endpoint"):
        return {"id": name, "name": name, "kind": kind, "participants": [{"name": p} for p in parts], "steps": [], "systems": []}
    fs = [flow("POST /api/cases/{case_id}/disseminate", ["api_gate", "dissemination", "Elasticsearch"]),
          flow("GET /api/cases/{case_id}/files", ["api_gate", "investigations"]),
          flow("ACTION disseminate_case", ["api_handler", "api_gate", "dissemination"])]
    hits = pa.rank(fs, pa.terms("flow of dissemination documents"), pa.flow_fields, 5)
    assert {h[1]["id"] for h in hits} == {fs[0]["id"], fs[2]["id"]}
    assert pa.rank(fs, pa.terms("billing invoices"), pa.flow_fields, 5) == []


def test_decision_search_reads_the_whole_adr():
    adrs = [{"number": 1, "title": "Use Kafka for events", "status": "accepted",
             "content": {"decision_outcome": "Asynchronous messages between ingest and query", "context": "", "consequences": ""}},
            {"number": 2, "title": "Cache search results", "status": "proposed",
             "content": {"decision_outcome": "Redis in front of Elasticsearch", "decision_drivers": ["latency"]}}]
    hits = pa.rank(adrs, pa.terms("is caching part of any decision?"), pa.adr_fields, 5)
    assert hits and hits[0][1]["number"] == 2
    assert "ADR-0002" in pa.adr_brief(adrs[1])


def test_flow_brief_keeps_the_order_of_participants():
    f = {"name": "ACTION x", "kind": "endpoint", "distributed": True, "systems": ["presenter", "gate", "service-data"],
         "participants": [{"name": n} for n in ("presenter", "gate", "service-data")],
         "steps": [{"from": "a", "to": "b", "kind": "calls", "label": "POST /gate/action_sync"}]}
    b = pa.flow_brief(f, {"a": "api_handler", "b": "api_gate"})
    assert "presenter -> gate -> service-data" in b and "api_handler -calls-> api_gate" in b

"""Documentation engine (AT-DOCUMENTATION_ENGINE-001/002), document splitting, assistant citations, model policy."""
import pytest

from archtwin.architecture.builder import build
from archtwin.common.errors import Problem
from archtwin.documents.engine import merge_manual, render
from archtwin.documents.service import sniff, split_markdown
from archtwin.intelligence import gateway
from archtwin.intelligence.assistant import validate_citations
from tests.conftest import edge, obs


def g():
    return build([obs("system:s", "software-system"), obs("container:s/api", "container", attrs={"technology": "Python"}),
                  obs("container:s/db", "container"), edge("system:s", "contains", "container:s/api"), edge("system:s", "contains", "container:s/db"),
                  edge("container:s/api", "writes", "container:s/db", attrs={"protocol": "postgresql"})])


def test_generated_doc_cites_evidence_for_every_element():
    body, ev, cov = render("system-overview", g(), "Shop", {"version": 3, "manifest_hash": "abcdef1234567890"})
    assert cov["ratio"] == 1.0 and ev and "[E1]" in body and "## Evidence" in body and "compose.yaml" in body


def test_manual_sections_survive_regeneration():
    old = "x\n<!-- archtwin:manual:intro -->\nMy words\n<!-- /archtwin:manual -->\ny"
    new = "z\n<!-- archtwin:manual:intro -->\n_placeholder_\n<!-- /archtwin:manual -->\nw"
    out = merge_manual(old, new)
    assert "My words" in out and "_placeholder_" not in out and out.startswith("z")


def test_markdown_escaping_of_untrusted_names_in_docs():
    gg = build([obs("system:s", "software-system"), obs("container:s/x", "container", name="<img src=x onerror=1>|"), edge("system:s", "contains", "container:s/x")])
    body, *_ = render("container-catalog", gg, "T", {"version": 1, "manifest_hash": "0" * 16})
    assert "<img" not in body


def test_split_markdown_keeps_line_provenance():
    ps = split_markdown("# A\npara1\n\n## B\nline\n```\n# not a heading\n```\n")
    assert [p["heading"] for p in ps] == ["A", "B"] and ps[1]["line_start"] == 4 and "# not a heading" in ps[1]["text"]


def test_upload_type_detected_by_magic_bytes_not_extension():
    assert sniff(b"%PDF-1.7 ...", "notes.md") == "application/pdf"
    assert sniff(b"\x00\x01\xff\xfe binary", "readme.md") == "application/octet-stream"
    assert sniff(b"# hello", "a.md") == "text/markdown"


def test_invalid_citations_are_removed_and_flagged():
    ev = [{"id": "E1"}, {"id": "E2"}]
    ans, good, bad = validate_citations("A [E1]. B [E9]. C [E2][E1].", ev)
    assert good == ["E1", "E2"] and bad == ["E9"] and "[E9]" not in ans and "[citation removed]" in ans


def test_model_policy_server_side():
    assert gateway.resolve_model(None, None) == "gpt-6-luna"
    assert gateway.resolve_model("gpt-6-sol", "gpt-6-terra") == "gpt-6-sol"
    assert gateway.resolve_model(None, "gpt-6-terra") == "gpt-6-terra"
    with pytest.raises(Problem):
        gateway.resolve_model("gpt-4o", None)
    gateway.mark_unavailable("gpt-6-terra")
    try:
        with pytest.raises(Problem):
            gateway.resolve_model("gpt-6-terra", None)
        assert gateway.resolve_model(None, "gpt-6-terra") == "gpt-6-luna"       # hidden, not degraded
        assert "gpt-6-terra" not in [m["alias"] for m in gateway.available()]
    finally:
        gateway._unavailable.clear()


async def test_fake_llm_mode_is_deterministic_and_cites():
    msgs = [{"role": "user", "content": "<evidence>\n[E1] (element) x\n[E2] (element) y\n</evidence>\nQ"}]
    a = await gateway.complete(msgs, model="gpt-6-luna", operation="t", project_id="p", user_id="u")
    b = await gateway.complete(msgs, model="gpt-6-luna", operation="t", project_id="p", user_id="u")
    assert a.text == b.text and "[E1]" in a.text and a.trace_id == "fake"

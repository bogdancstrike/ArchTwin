"""AT-DIAGRAM_STUDIO-005/006/007 + 2.5 exports: budget, focal, linter, zoom levels, escaping (XSS corpus)."""
import json
from pathlib import Path

import pytest

from archtwin.architecture.builder import build
from archtwin.connectors.analyzers.repo import analyze_repository
from archtwin.diagrams import render
from archtwin.diagrams.export import mermaid_text, to_mermaid, to_structurizr
from archtwin.diagrams.views import build_view
from tests.conftest import edge, obs

ROOT = Path(__file__).resolve().parents[4]
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "sample_repo"


@pytest.fixture(scope="module")
def shop():
    r = analyze_repository(FIX, "r", "shop")
    return build([{**o.model_dump(), "id": i, "connector_id": None, "observed_at": None} for i, o in enumerate(r.observations)])


def big_system(n=14):
    o = [obs("system:big", "software-system")]
    for i in range(n):
        o += [obs(f"container:big/c{i}", "container", attrs={"subtype": "database" if i % 4 == 0 else "service"}),
              edge("system:big", "contains", f"container:big/c{i}")]
        if i:
            o.append(edge(f"container:big/c{i}", "calls", f"container:big/c{i - 1}", attrs={"protocol": "http"}))
    return build(o)


def test_overview_split_above_nine_primary_nodes_with_detail_views():
    v = build_view(big_system(14), "system:big")
    assert v["budget"]["split"] and v["budget"]["primary"] <= 9 and v["detail_views"]
    detail = build_view(big_system(14), v["detail_views"][0]["key"])
    assert detail["level"] == 2 and detail["breadcrumbs"][-1]["key"] == v["detail_views"][0]["key"]


def test_at_most_two_focal_elements_and_drift_is_focal():
    g = big_system(14)
    v = build_view(g, "system:big", drift_keys={"container:big/c3|calls|container:big/c2", "container:big/c5", "container:big/c7"})
    focal = [x for x in v["nodes"] + v["edges"] if x.get("focal")]
    assert 1 <= len(focal) <= 2 and all(x.get("focal_reason") == "drift" for x in focal)


def test_c4_zoom_context_to_container_to_component(shop):
    ctx = build_view(shop, "context")
    s = next(n for n in ctx["nodes"] if n["kind"] == "system")
    l2 = build_view(shop, s["zoom"])
    api = next(n for n in l2["nodes"] if n["id"] == "container:shop/api")
    l3 = build_view(shop, api["zoom"])
    assert [b["title"] for b in l3["breadcrumbs"]] == ["Context", "shop", "api"] and l3["level"] == 3 and l3["nodes"]


def test_no_component_level_evidence_is_explicit(shop):
    v = build_view(shop, "container:shop/db")
    assert v["nodes"] == [] and "No component-level evidence" in v["empty_reason"]


def test_generated_views_pass_the_linter(shop):
    for key in ("context", "system:shop", "container:shop/api", "container:shop/worker"):
        lay = render.layout_and_lint(build_view(shop, key))
        assert lay.violations == [], (key, lay.violations)


def test_linter_blocks_broken_layout():
    v = {"nodes": [{"id": "a", "primary": True}, {"id": "b", "primary": True}, {"id": "c", "primary": True}],
         "edges": [{"id": "e1", "source": "a", "target": "b", "label": "x"}, {"id": "e2", "source": "a", "target": "c", "label": "y"}]}
    boxes = {"a": render.Box("a", 0, 0), "b": render.Box("b", 400, 0), "c": render.Box("c", 200, 0)}
    routes = [render.Routed("e1", [(184, 30), (400, 30)], [("a", "R", 30), ("b", "L", 30)], "x", (250, 20, 30, 14)),
              render.Routed("e2", [(184, 30), (200, 30)], [("a", "R", 30), ("c", "L", 30)], "y", (190, 25, 30, 14)),
              ]
    lay = render.Layout(boxes, routes, 600, 100)
    rules = {x["rule"] for x in render.lint(v, lay)}
    assert {"fanned-attach-points", "no-overlapping-connectors", "no-transit-behind-box", "no-label-under-node"} <= rules


def test_linter_rejects_diagonals_and_budget():
    v = {"nodes": [{"id": str(i), "primary": True, "focal": i < 3} for i in range(10)], "edges": [{"id": "e", "source": "0", "target": "1"}]}
    boxes = {str(i): render.Box(str(i), i * 300, 0) for i in range(10)}
    lay = render.Layout(boxes, [render.Routed("e", [(184, 10), (300, 50)], [("0", "R", 10), ("1", "L", 50)])], 3000, 100)
    rules = {x["rule"] for x in render.lint(v, lay)}
    assert {"orthogonal-rounded", "complexity-budget", "focal-budget"} <= rules


def test_svg_export_uses_org_tokens_only(shop):
    v = build_view(shop, "system:shop")
    svg = render.to_svg(v, render.layout_and_lint(v), {"paper": "#101010", "accent": "#00ff00"})
    assert "#101010" in svg and render.TOKENS["light"]["paper"] not in svg


XSS = ['<script>alert(1)</script>', '"><img src=x onerror=alert(1)>', "javascript:alert(1)", "a]-->b[\"x\"]", "`${x}`|{y}"]


@pytest.mark.parametrize("payload", XSS)
def test_mermaid_and_dsl_escape_untrusted_names(payload):
    g = build([obs("system:s", "software-system", name=payload), obs("container:s/x", "container", name=payload),
               edge("system:s", "contains", "container:s/x")])
    m = to_mermaid(build_view(g, "system:s"))
    assert "<script" not in m and "<img" not in m and "securityLevel': 'strict'" in m
    assert all(ch not in mermaid_text(payload) for ch in '<>"`|[]{}')
    dsl = to_structurizr(g, payload)
    for line in dsl.splitlines():
        assert line.count('"') % 2 == 0 or '\\"' in line


def test_svg_escapes_names():
    g = build([obs("system:s", "software-system"), obs("container:s/x", "container", name="<script>x</script>"), edge("system:s", "contains", "container:s/x")])
    v = build_view(g, "system:s")
    assert "<script>" not in render.to_svg(v, render.layout_and_lint(v))


def test_design_tokens_in_sync_across_packages():
    canon = json.loads((ROOT / "packages/diagram-design-system/tokens.json").read_text())
    assert canon == json.loads((ROOT / "apps/api/archtwin/diagrams/tokens.json").read_text())
    assert canon == json.loads((ROOT / "apps/web/src/diagram/tokens.json").read_text())

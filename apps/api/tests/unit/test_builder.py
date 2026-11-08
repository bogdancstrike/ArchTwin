"""AT-ARCHITECTURE_GRAPH-002/004: deterministic builder, aliases, precedence, diff."""
import random

from archtwin.architecture.builder import build, diff, suggestions
from tests.conftest import edge, obs


def sample():
    return [obs("system:s", "software-system"), obs("container:s/api", "container", attrs={"technology": "Python"}),
            obs("container:s/db", "container", attrs={"subtype": "database"}),
            edge("system:s", "contains", "container:s/api"), edge("container:s/api", "writes", "container:s/db", attrs={"protocol": "postgresql"})]


def test_same_inputs_same_manifest_regardless_of_order():
    a = sample()
    b = list(a)
    random.Random(4).shuffle(b)
    assert build(a)["manifest_hash"] == build(b)["manifest_hash"]


def test_rescan_with_new_observation_ids_keeps_manifest():
    assert build(sample())["manifest_hash"] == build(sample())["manifest_hash"]   # new ids/timestamps, same facts


def test_attribute_change_changes_manifest_and_diff_reports_it():
    a, b = sample(), sample()
    b[4] = edge("container:s/api", "writes", "container:s/db", attrs={"protocol": "mysql"})
    ga, gb = build(a), build(b)
    assert ga["manifest_hash"] != gb["manifest_hash"]
    d = diff(ga, gb)
    assert d["edges"]["changed"][0]["fields"] == ["protocol"] and d["summary"]["nodes_added"] == 0


def test_manual_origin_takes_precedence_for_name_and_attributes():
    g = build(sample() + [obs("container:s/api", "container", origin="manual", name="Orders API", attrs={"technology": "FastAPI"})])
    n = g["nodes"]["container:s/api"]
    assert n["name"] == "Orders API" and n["attributes"]["technology"] == "FastAPI" and n["origins"][0] == "manual"


def test_alias_merges_runtime_identity_into_static_key():
    rt = obs("container:docker/shop-api-1", "container", origin="runtime", attrs={"state": "running"})
    g = build(sample() + [rt], {"container:docker/shop-api-1": "container:s/api"})
    assert "container:docker/shop-api-1" not in g["nodes"]
    assert set(g["nodes"]["container:s/api"]["origins"]) == {"static", "runtime"}


def test_edges_with_missing_endpoints_are_dropped_not_invented():
    g = build(sample() + [edge("container:s/api", "calls", "container:s/ghost")])
    assert "container:s/api|calls|container:s/ghost" in g["dropped_edges"] and "container:s/ghost" not in g["nodes"]


def test_inferred_only_elements_are_flagged():
    g = build(sample() + [obs("external:openai", "external-system", origin="inferred", conf=0.6)])
    assert g["nodes"]["external:openai"]["inferred_only"] is True
    assert g["nodes"]["container:s/api"]["inferred_only"] is False


def test_manual_retraction_removes_element():
    g = build(sample() + [obs("container:s/db", "container", origin="manual", attrs={"retracted": True})])
    assert "container:s/db" not in g["nodes"] and not any("container:s/db" in k for k in g["edges"])


def test_identity_suggestions_for_same_name_different_origins():
    g = build(sample() + [obs("container:docker/api", "container", origin="runtime")])
    assert any({a, b} == {"container:docker/api", "container:s/api"} for a, b, *_ in suggestions(g["nodes"]))

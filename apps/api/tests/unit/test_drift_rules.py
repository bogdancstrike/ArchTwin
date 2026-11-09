"""AT-DRIFT_ENGINE-001..003 truth table (phase-04 design.md) + stable identity."""
import uuid

from archtwin.architecture.builder import build
from archtwin.drift.rules import Coverage, evaluate, finding_id
from tests.conftest import edge, obs

P = uuid.uuid4()


def base_graph(extra=()):
    return build([obs("system:s", "software-system"), obs("container:s/api", "container"), obs("container:s/db", "container"),
                  edge("container:s/api", "writes", "container:s/db", attrs={"protocol": "postgresql"}), *extra])


def cov(static="current", runtime=None):
    inputs = [{"coverage": {"origin": "static", "prefixes": ["container:s/", "system:s"]}, "freshness": {"status": static}}]
    if runtime:
        inputs.append({"coverage": {"origin": "runtime", "prefixes": ["container:s/"]}, "freshness": {"status": runtime}})
    return Coverage.from_inputs(inputs)


def rules_of(fs, verdict=None):
    return {(f["rule_id"], f["subject_key"]) for f in fs if verdict is None or f["verdict"] == verdict}


def test_in_sync_produces_nothing():
    g = base_graph()
    assert evaluate(g, g, cov()) == []


def test_missing_with_fresh_complete_coverage_is_drift():
    cur = build([obs("system:s", "software-system"), obs("container:s/api", "container")])
    fs = evaluate(base_graph(), cur, cov("current"))
    assert ("DR-MISSING-001", "container:s/db") in rules_of(fs, "drift")


def test_missing_with_stale_coverage_raises_nothing():
    """Not observed by a stale/absent source says nothing: no drift and no 'no longer observed' finding at all."""
    cur = build([obs("system:s", "software-system"), obs("container:s/api", "container")])
    fs = evaluate(base_graph(), cur, cov("stale"))
    assert ("DR-MISSING-001", "container:s/db") not in rules_of(fs)
    assert not rules_of(fs, "drift")


def test_missing_with_partial_coverage_is_incomplete():
    cur = build([obs("system:s", "software-system"), obs("container:s/api", "container")])
    assert ("DR-MISSING-001", "container:s/db") in rules_of(evaluate(base_graph(), cur, cov("incomplete")), "incomplete")


def test_uncovered_element_is_unknown():
    cur = build([obs("system:s", "software-system")])
    fs = evaluate(base_graph(), cur, Coverage.from_inputs([]))
    assert all(f["verdict"] == "unknown" for f in fs if f["rule_id"] == "DR-MISSING-001")


def test_unplanned_element_and_edge():
    cur = base_graph([obs("container:s/cache", "container"), edge("container:s/api", "calls", "container:s/cache")])
    r = rules_of(evaluate(base_graph(), cur, cov()), "drift")
    assert ("DR-UNPLANNED-001", "container:s/cache") in r and ("DR-EDGE-ADDED-001", "container:s/api|calls|container:s/cache") in r


def test_protocol_changed():
    cur = build([obs("system:s", "software-system"), obs("container:s/api", "container"), obs("container:s/db", "container"),
                 edge("container:s/api", "writes", "container:s/db", attrs={"protocol": "mysql"})])
    assert ("DR-PROTOCOL-001", "container:s/api|writes|container:s/db") in rules_of(evaluate(base_graph(), cur, cov()))


def test_inferred_or_low_confidence_evidence_never_raises_unplanned():
    cur = base_graph([obs("external:x", "external-system", origin="inferred", conf=0.5)])
    assert not rules_of(evaluate(base_graph(), cur, cov()))


def test_declared_not_running_needs_runtime_coverage():
    g = base_graph()
    assert not evaluate(None, g, cov(runtime=None))                                       # no runtime connector: silent
    r = evaluate(None, g, cov(runtime="current"))
    assert ("DR-RUNTIME-NOT-RUNNING-001", "container:s/api") in rules_of(r, "drift")
    r2 = evaluate(None, g, cov(runtime="stale"))
    assert all(f["verdict"] == "unknown" for f in r2)


def test_running_and_declared_is_in_sync_and_optional_services_are_ignored():
    g = build([obs("system:s", "software-system"), obs("container:s/api", "container"), obs("container:s/api", "container", origin="runtime",
               attrs={"running": True}), obs("container:s/jaeger", "container", attrs={"optional": True})])
    fs = evaluate(None, g, cov(runtime="current"))
    assert not fs


def test_running_but_undeclared():
    g = base_graph([obs("container:s/rogue", "container", origin="runtime", attrs={"running": True})])
    assert ("DR-RUNTIME-UNDECLARED-001", "container:s/rogue") in rules_of(evaluate(None, g, cov(runtime="current")))


def test_no_baseline_only_runtime_rules_apply():
    assert all(f["rule_id"].startswith("DR-RUNTIME") for f in evaluate(None, base_graph(), cov(runtime="current")))


def test_reevaluation_is_idempotent_and_ids_are_stable():
    cur = build([obs("system:s", "software-system"), obs("container:s/api", "container")])
    strip = lambda fs: [{k: v for k, v in f.items() if k != "evidence"} for f in fs]  # noqa: E731
    a, b = evaluate(base_graph(), cur, cov()), evaluate(base_graph(), cur, cov())
    assert strip(a) == strip(b)                       # same facts => same findings (evidence ids differ per build)
    assert finding_id(P, "DR-MISSING-001", "container:s/db") == finding_id(P, "DR-MISSING-001", "container:s/db")
    assert finding_id(P, "DR-MISSING-001", "container:s/db") != finding_id(uuid.uuid4(), "DR-MISSING-001", "container:s/db")



def test_external_dependency_no_longer_inferred_is_not_drift():
    """'external:elasticsearch is no longer observed' after an analyzer change is noise, not a missing element."""
    base = base_graph([obs("external:elasticsearch", "external-system")])
    fs = evaluate(base, base_graph(), cov())
    assert not any(f["subject_key"] == "external:elasticsearch" for f in fs)


def test_rekeyed_element_with_the_same_name_is_not_missing_and_its_edges_are_not_removed():
    base = base_graph()
    cur = build([obs("system:s", "software-system"), obs("container:s/api", "container"), obs("container:s/x-db", "container", name="db"),
                 edge("container:s/api", "writes", "container:s/x-db", attrs={"protocol": "postgresql"})])
    fs = evaluate(base, cur, cov())
    assert not [f for f in fs if f["rule_id"] in ("DR-MISSING-001", "DR-EDGE-REMOVED-001")]

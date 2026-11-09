"""AT-SOURCE_CODE_DISCOVERY: static analyzers vs labelled ground truth (precision/recall, task 3.4); secrets never read."""
from pathlib import Path

import yaml

from archtwin.connectors.analyzers.repo import analyze_repository
from archtwin.connectors.sdk import Observation

FIX = Path(__file__).resolve().parents[1] / "fixtures"
ARCH = ("container", "endpoint", "component", "external", "person", "system")


def scan():
    return analyze_repository(FIX / "sample_repo", "rev1", "shop")


def test_recall_against_ground_truth_is_complete():
    r = scan()
    keys = {o.subject_key for o in r.observations}
    gt = yaml.safe_load((FIX / "ground-truth.yaml").read_text())
    missing = [k for k in gt["nodes"] + gt["edges"] if k not in keys]
    assert not missing, missing


def test_precision_of_runtime_relationships():
    """Every inferred calls/writes edge between containers must be in the ground truth (no invented wiring)."""
    r = scan()
    gt = set(yaml.safe_load((FIX / "ground-truth.yaml").read_text())["edges"])
    rels = {o.subject_key for o in r.observations if o.subject_kind == "edge" and o.kind in ("calls", "writes")
            and "name:" not in o.subject_key}                    # name: refs are resolved (or dropped) by the graph builder
    assert rels <= gt, rels - gt


def test_every_observation_carries_provenance():
    for o in scan().observations:
        assert isinstance(o, Observation) and o.parser_version and o.source_revision == "rev1" and 0 <= o.confidence <= 1


def test_secret_files_never_read_and_urls_without_credentials():
    r = scan()
    dump = str([o.model_dump() for o in r.observations]) + str([d.text for d in r.documents])
    assert "ARCHTWIN-CANARY" not in dump and "supersecret" not in dump
    assert all("@" not in str(o.attributes.get("url", "")) for o in r.observations)


def test_one_shot_jobs_and_docs_and_adrs_detected():
    r = scan()
    nodes = {o.subject_key: o for o in r.observations if o.subject_kind == "node" and o.parser_version.startswith(("compose", "markdown"))}
    assert nodes["container:shop/migrate"].attributes["one_shot"] is True
    assert {d.path for d in r.documents} >= {"README.md", "docs/adr/0001-use-postgresql.md"}
    assert any(k.startswith("adr:shop/") for k in nodes)


def test_endpoints_only_for_http_serving_containers():
    r = scan()
    eps = [o.subject_key for o in r.observations if o.kind == "api-endpoint" and "/contract/" not in o.subject_key]
    assert eps and all(k.startswith("endpoint:shop/api/") for k in eps)


def test_owners_from_codeowners():
    r = scan()
    owners = {o.subject_key: o.attributes["owner"] for o in r.observations if "owner" in o.attributes}
    assert owners.get("container:shop/api") in ("@orders-team", "@platform-team")


def test_scan_is_deterministic():
    a, b = scan(), scan()
    assert [o.model_dump() for o in a.observations] == [o.model_dump() for o in b.observations]

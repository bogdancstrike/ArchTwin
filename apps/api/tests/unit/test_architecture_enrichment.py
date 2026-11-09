"""Comprehensive architecture from every datasource: cross-repository wiring, documented diagrams, ADR/work-item mentions."""
import uuid
from datetime import UTC, datetime
from pathlib import Path

from archtwin.architecture import builder
from archtwin.connectors.analyzers.repo import analyze_repository, diagram_edges, name_ref


def _obs(result, connector):
    return [{"id": uuid.uuid4(), "connector_id": connector, "origin": o.origin, "subject_kind": o.subject_kind, "subject_key": o.subject_key,
             "kind": o.kind, "name": o.name, "attributes": o.attributes, "source_ref": o.source_ref, "source_revision": o.source_revision,
             "evidence": o.evidence, "observed_at": datetime.now(UTC), "parser_version": o.parser_version, "confidence": o.confidence,
             "sensitive": o.sensitive} for o in result.observations]


def _write(root: Path, files: dict[str, str]) -> Path:
    for k, v in files.items():
        (root / k).parent.mkdir(parents=True, exist_ok=True)
        (root / k).write_text(v)
    return root


def test_name_ref_only_for_service_like_hosts():
    assert name_ref("service-iam") == "name:service-iam"
    assert name_ref("orders.shop.svc.cluster.local") == "name:orders"
    assert [name_ref(h) for h in ("localhost", "10.1.2.3", "api.github.com", "${HOST}")] == [None, None, None, None]


def test_cross_repository_calls_resolve_across_datasources(tmp_path):
    data = analyze_repository(_write(tmp_path / "service-data", {"compose.yaml":
        "services:\n  service-data:\n    image: python:3.12\n    environment:\n      IAM_URL: http://service-iam:8080/api\n"
        "      SEARCH: http://nowhere-svc:9200\n"}), "r1", "service-data")
    iam = analyze_repository(_write(tmp_path / "service-iam", {"compose.yaml": "services:\n  service-iam:\n    image: python:3.12\n"}), "r2", "service-iam")
    g = builder.build(_obs(data, "c1") + _obs(iam, "c2"))
    e = g["edges"]["container:service-data/service-data|calls|container:service-iam/service-iam"]
    assert e["attributes"]["resolved_by"] == "name" and e["origins"] == ["static"] and e["confidence"] == 0.7
    assert "nowhere-svc" in g["unresolved_names"]                                  # unknown name: dropped and reported
    assert not any("name:" in k for k in g["edges"])


def test_ambiguous_names_are_never_guessed():
    n = lambda k, kind="container": {"key": k, "kind": kind, "name": k.rsplit("/", 1)[-1], "attributes": {}}     # noqa: E731
    nodes = {k: n(k) for k in ("container:a/api", "container:b/api", "container:a/web")}
    edges = {"container:a/web|calls|name:api": {"key": "container:a/web|calls|name:api", "kind": "calls", "source": "container:a/web",
                                                 "target": "name:api", "attributes": {}, "by_origin": {}, "origins": {"static"},
                                                 "confidence": 0.7, "evidence": []}}
    assert builder.resolve_names(nodes, edges) == ["api"] and edges == {}


def test_documented_diagram_corroborates_code_and_adds_dashed_relations(tmp_path):
    repo = analyze_repository(_write(tmp_path / "shop", {
        "compose.yaml": "services:\n  orders:\n    image: python:3.12\n    environment:\n      DB: postgresql://orders-db:5432/x\n"
                        "  orders-db:\n    image: postgres:17\n  billing:\n    image: python:3.12\n",
        "docs/architecture.md": "# Arch\n\n```mermaid\nflowchart LR\n  o[orders] -- writes orders --> db[(orders-db)]\n  o -- publishes invoices --> b(billing)\n"
                                "  o --> ghost[Ghost service]\n```\n"}), "r", "shop")
    g = builder.build(_obs(repo, "c"))
    both = g["edges"]["container:shop/orders|writes|container:shop/orders-db"]
    assert both["origins"] == ["static", "inferred"] and not both["inferred_only"]       # code and the documented diagram agree
    doc = g["edges"]["container:shop/orders|publishes|container:shop/billing"]
    assert doc["origins"] == ["inferred"] and doc["inferred_only"] and doc["attributes"]["documented"] is True
    assert doc["attributes"]["diagram"] == "docs/architecture.md"
    assert "Ghost service" in g["unresolved_names"]


def test_diagram_parsers():
    assert ("service-data", "publishes", "Kafka", "publishes events") in diagram_edges(
        "mermaid", "flowchart LR\n data(service-data) -- publishes events --> k[(Kafka)]\n")
    assert diagram_edges("plantuml", 'component "Service IAM" as iam\n[service-data] --> iam : verify token') == \
        [("service-data", "calls", "Service IAM", "verify token")]
    assert diagram_edges("structurizr", 'a = container "A svc"\nb = container "B svc"\na -> b "Writes rows"') == [("A svc", "writes", "B svc", "Writes rows")]
    assert diagram_edges("mermaid", "flowchart LR\n user --> api\n") == []                      # generic actor names skipped


def test_adrs_and_work_items_link_to_named_elements():
    def node(k, kind, name, **attrs):
        return {"id": uuid.uuid4(), "connector_id": "c", "origin": "issue" if kind == "work-item" else "static", "subject_kind": "node",
                "subject_key": k, "kind": kind, "name": name, "attributes": attrs, "source_ref": "x", "source_revision": "r", "evidence": {},
                "observed_at": datetime.now(UTC), "parser_version": "t", "confidence": 1.0, "sensitive": False}
    g = builder.build([node("container:qsint/service-data", "container", "service-data"), node("container:qsint/api", "container", "api"),
                       node("work-item:taiga/q#6", "work-item", "#6 Service data export timeout in the API"),
                       node("adr:arch/ADRs/ADR-001.md", "adr", "ADR-001 Partition service_data tables")])
    assert "work-item:taiga/q#6|references|container:qsint/service-data" in g["edges"]      # "Service data" ~ service-data
    assert "adr:arch/ADRs/ADR-001.md|references|container:qsint/service-data" in g["edges"]
    assert not any(k.endswith("|container:qsint/api") for k in g["edges"])                  # generic names never linked
    e = g["edges"]["work-item:taiga/q#6|references|container:qsint/service-data"]
    assert e["inferred_only"] and e["confidence"] == 0.5

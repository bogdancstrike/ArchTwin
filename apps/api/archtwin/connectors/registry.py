"""Connector registry: kind -> implementation. Each kind is gated by `module.connector-platform` + its module + provider flag."""
from archtwin.connectors.adapters.docker_engine import DockerEngineConnector
from archtwin.connectors.adapters.git_repo import GitRepoConnector
from archtwin.connectors.adapters.github import GitHubConnector
from archtwin.connectors.adapters.gitlab import GitLabConnector
from archtwin.connectors.adapters.http_openapi import HttpOpenApiConnector
from archtwin.connectors.adapters.kafka_cluster import KafkaClusterConnector
from archtwin.connectors.adapters.otel_servicegraph import OtelServiceGraphConnector
from archtwin.connectors.adapters.sql_catalog import MySqlCatalogConnector, PostgresCatalogConnector
from archtwin.connectors.adapters.taiga import TaigaConnector

REGISTRY = {c.kind: c for c in (GitRepoConnector(), GitHubConnector(), GitLabConnector(), TaigaConnector(), DockerEngineConnector(),
                                OtelServiceGraphConnector(), PostgresCatalogConnector(), MySqlCatalogConnector(), KafkaClusterConnector(),
                                HttpOpenApiConnector())}
MODULE_FLAG = {"git": "module.source-code-discovery", "github": "module.source-code-discovery", "gitlab": "module.source-code-discovery",
               "taiga": "module.work-connectors",
               "docker": "module.runtime-discovery", "otel_servicegraph": "module.runtime-discovery", "http_openapi": "module.runtime-discovery",
               "postgresql": "module.data-topology", "mysql": "module.data-topology", "kafka": "module.data-topology"}
CATEGORY = {"git": "code", "github": "code", "gitlab": "code", "taiga": "work", "docker": "runtime", "otel_servicegraph": "runtime",
            "http_openapi": "api", "postgresql": "data", "mysql": "data", "kafka": "messaging"}


def get(kind: str):
    return REGISTRY.get(kind)


def manifests() -> list[dict]:
    return [{"kind": k, "flag": c.flag, "module_flag": MODULE_FLAG[k], "category": CATEGORY[k], **c.manifest} for k, c in REGISTRY.items()]

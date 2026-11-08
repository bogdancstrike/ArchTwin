"""Connector registry: kind -> implementation. Each kind is gated by `module.connector-platform` + its provider flag."""
from archtwin.connectors.adapters.docker_engine import DockerEngineConnector
from archtwin.connectors.adapters.git_repo import GitRepoConnector
from archtwin.connectors.adapters.http_openapi import HttpOpenApiConnector
from archtwin.connectors.adapters.postgres_catalog import PostgresCatalogConnector

REGISTRY = {c.kind: c for c in (GitRepoConnector(), DockerEngineConnector(), PostgresCatalogConnector(), HttpOpenApiConnector())}
MODULE_FLAG = {"git": "module.source-code-discovery", "docker": "module.runtime-discovery", "postgresql": "module.data-topology",
               "http_openapi": "module.runtime-discovery"}


def get(kind: str):
    return REGISTRY.get(kind)


def manifests() -> list[dict]:
    return [{"kind": k, "flag": c.flag, "module_flag": MODULE_FLAG[k], **c.manifest} for k, c in REGISTRY.items()]

"""Runtime configuration (12-factor, ARCHTWIN_* environment variables)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARCHTWIN_", extra="ignore")

    database_url: str = "postgresql+asyncpg://archtwin_app:archtwin@localhost:5452/archtwin"
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    task_queue: str = "archtwin"
    cerbos_url: str = "http://localhost:3592"
    oidc_issuer: str = "http://localhost:8280/realms/archtwin"
    oidc_jwks_url: str = "http://localhost:8280/realms/archtwin/protocol/openid-connect/certs"
    oidc_audience: str = "archtwin-api"
    kek: str = ""                      # base64 32-byte key-encryption key (dev KeyProvider)
    kek_id: str = "local-v1"
    llm_mode: str = "fake"             # litellm | fake
    llm_base_url: str = "http://localhost:4200/v1"
    llm_api_key: str = ""
    llm_timeout_s: float = 120.0
    valkey_url: str = ""
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "archtwin"
    log_level: str = "info"
    local_source_roots: str = "/sources"
    egress_allow_private_hosts: str = ""
    docling_url: str = ""
    max_upload_mb: int = 25
    default_org_name: str = "Demo Organization"
    graph_debounce_s: float = 3.0

    @property
    def source_roots(self) -> list[str]:
        return [p.strip() for p in self.local_source_roots.split(",") if p.strip()]

    @property
    def private_host_allowlist(self) -> set[str]:
        return {h.strip() for h in self.egress_allow_private_hosts.split(",") if h.strip()}


@lru_cache
def settings() -> Settings:
    return Settings()

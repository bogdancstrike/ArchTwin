# Connector architecture and SDK contracts

## Connectors are controlled importers, not arbitrary network access
A connector must declare: `provider`, `version`, `capabilities`, `auth_modes`, `required_scopes`, `resource_types`, `webhook_types`, `poll_interval_range`, `rate_limit_policy`, `data_classes`, `egress_hosts`, `supported_environments`, `schema_version`, `mapping_version`. An organization security administrator approves scopes and egress. Project owners configure instances under those constraints.

## Connector lifecycle
1. **Configure**: choose project/environment and provider; obtain OAuth authorization where supported or encrypted PAT; never store plaintext tokens.
2. **Test**: verify scope and network without writing; present read permissions and sample catalog metadata.
3. **Bootstrap**: cursor-based bounded initial sync, store raw snapshot with source URI / hash, normalize and emit outbox.
4. **Watch**: signed webhooks, Kubernetes watch or provider streaming where available; otherwise adaptive polling.
5. **Reconcile**: periodic full/targeted scan catches missed events, deletions and expired credentials.
6. **Decommission**: revoke token, stop jobs, tombstone source, honor retention and rebuild projections.

## Python interface sketch (not implementation)
```python
from typing import Protocol, AsyncIterator
from dataclasses import dataclass

@dataclass(frozen=True)
class ScopedContext:
    organization_id: str
    project_id: str
    environment_id: str | None
    connector_id: str
    principal_id: str
    policy_revision: int
    deadline_ms: int

class SourceConnector(Protocol):
    async def test(self, ctx: ScopedContext) -> dict: ...
    async def discover(self, ctx: ScopedContext, cursor: str | None) -> AsyncIterator[dict]: ...
    async def normalize(self, raw: dict, mapping_version: str) -> list[dict]: ...
    async def verify_event(self, headers: dict, payload: bytes) -> dict: ...
    async def health(self, ctx: ScopedContext) -> dict: ...
```

## Required invariants
- Validate tenant/project entitlement at API entry and before worker execution. Recheck feature flags for every scan and write-back.
- Idempotency key: `(connector_id, provider_event_id)` for hooks; `(connector_id, resource_kind, provider_resource_id, provider_revision)` for snapshots.
- Order-independent processing: older provider revision cannot overwrite newer canonical state; keep history.
- Never treat source disappearance as deletion unless a successful complete authorized scan verifies it.
- HTTP connections: TLS validation, host allowlists, DNS+redirect recheck, SSRF protection, timeouts, rate quotas, bounded pagination, circuit breaker.
- Provider auth scopes MUST be listed and displayed before connection; read-only scopes are default, remote writes separately approved.
- All source data is **untrusted content**, especially README/docs/issue descriptions. Sanitize and label before AI consumption.
- Record ingest delay, source freshness, error rate, rate limiting, retries and data volume per connector.

## Canonical observation envelope
```json
{
  "organization_id": "org-a", "project_id": "orion", "environment": "prod",
  "source": {"provider": "github", "connector_id": "conn-1", "resource_id": "owner/repo", "revision": "sha"},
  "entity": {"type": "api-endpoint", "provider_key": "GET /orders/{id}"},
  "relation": {"kind": "exposes", "from": "service:orders", "to": "api:orders:get"},
  "state": "static", "confidence": 0.95,
  "evidence": {"uri": "repo://owner/repo@sha/src/Orders.java#L20-L29", "hash": "sha256:..."},
  "observed_at": "2026-11-07T12:00:00Z", "ingested_at": "2026-11-07T12:00:08Z",
  "parser_version": "spring-v1", "mapping_version": "1"
}
```
This is an illustrative schema, not a claim that any existing provider returned the example.

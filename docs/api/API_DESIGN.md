# REST, event and streaming API design

All endpoint paths are versioned under `/api/v1`. Every read and mutation derives org/principal from verified OIDC claims + server-side memberships; never authorize based solely on path IDs. GET/list endpoints apply Cerbos PlanResources or explicit allowed-ID filters and record audit where sensitive. Every write uses `If-Match` or explicit revision and idempotency keys where needed.

## Primary resource APIs
| Group | Examples | Notes |
|---|---|---|
| Projects/environments | `POST /projects`, `GET /projects/{id}`, `POST /projects/{id}/environments` | scope, classification, membership |
| Connectors | `POST /projects/{id}/connectors`, `POST /connectors/{id}:test`, `POST /connectors/{id}:sync`, `GET /connectors/{id}/health` | encrypted credentials; read-only test |
| Architecture | `GET /projects/{id}/architecture?environment=prod&at=...`, `POST /projects/{id}/baselines`, `GET /snapshots/{id}/diff?to=...` | separate desired/static/observed |
| Diagrams | `POST /projects/{id}/diagrams:generate`, `PATCH /diagrams/{id}`, `GET /diagrams/{id}/versions`, `POST /diagrams/{id}:export` | draft vs accepted |
| Documents/ADRs | `POST /projects/{id}/documents`, `POST /adrs`, `POST /adrs/{id}:submit`, `POST /adrs/{id}:approve` | comments, version, review policy |
| Drift | `GET /projects/{id}/drift`, `GET /drift/{id}/evidence`, `POST /drift/{id}:acknowledge`, `POST /drift/{id}:suppress` | rule and evidence version |
| Plans/tasks | `POST /projects/{id}/initiatives`, `GET /initiatives/{id}/progress`, `POST /tasks/{id}:link`, `POST /tasks/{id}:preview-remote-write` | issue source remains authoritative for issue status |
| Federation | `POST /projects/{id}/federation-requests`, `POST /federation/{id}:approve`, `DELETE /federation/{id}` | bilateral grant, expiry |
| AI | `POST /projects/{id}/assistant:ask`, `POST /projects/{id}/integrations:design`, `POST /ai/proposals/{id}:preview`, `POST /ai/proposals/{id}:apply` | async job, approved evidence pack, cost budget |
| Flags | `GET /feature-flags/effective`, `PATCH /feature-flags/{key}` | globally safe precedence; audit |
| Alerts and reports | `GET /projects/{id}/alerts`, `GET /projects/{id}/health`, `POST /projects/{id}/exports` | ACL revalidated per export |

## API response contracts
```json
{
  "data": {"project_id":"prj-1","snapshot_id":"snap-2026-11-07"},
  "meta": {"trace_id":"trace-id","evidence_freshness":"current","policy_revision":15},
  "links": {"self":"/api/v1/projects/prj-1/architecture"}
}
```
Errors use RFC 9457-style problem details (`type`, `title`, `status`, `detail`, `trace_id`) without sensitive object names for forbidden resources. Query responses include `last_observed_at`, `stale`, and `completeness` fields when applicable.

## Events
`project.created`, `connector.synced`, `inventory.changed`, `architecture.snapshot.created`, `baseline.published`, `drift.detected`, `drift.resolved`, `adr.accepted`, `work_item.updated`, `federation.revoked`, `flag.changed`, `ai.run.completed`. Every event has `event_id`, `org_id`, `project_id`, `occurred_at`, `aggregate_revision`, `trace_id`, `schema_version` and no raw secrets. Consumers are idempotent.

## Real-time UI
Use authorized Server-Sent Events for project-scoped `drift`, `sync`, `plan` and `AI streaming` updates with replay cursors. Do not create a new websocket for every event type. Revalidate permissions on stream subscription and on sensitive replay. Never put raw model tokens or secret data into global broadcast channels.

## Contract acceptance
OpenAPI compatibility lint, generated TS SDK, contract tests for every route; pagination and p95 query limits; 401/403/404 semantics (no existence leaks); tenant isolation property tests; correct idempotency and concurrent-edit conflict resolution.

# Suggested implementation monorepo layout

```text
archtwin/
  apps/
    api/                          # FastAPI application and dependency injection
      archtwin/
        organizations/
        projects/
        iam/
        flags/
        audit/
        connectors/
        inventory/
        architecture/
        diagrams/
        documents/
        decisions/
        drift/
        planning/
        intelligence/
        notifications/
        common/                   # minimal kernel: principal, IDs, event/outbox, policy ports
    worker/                       # async source scanners, parsers, notifier, idempotent sync
    web/                          # React/Vite/TS/shadcn/ui
  packages/
    connector_sdk/                # adapter protocol, conformance test fixtures
    model_contracts/              # JSON Schema/OpenAPI generated contracts
    diagram-design-system/        # vendored diagram-design references (MIT) + tokens, type router,
                                  # node treatments, orthogonal router post-processor, linter
  fixtures/                       # OpenTelemetry Demo on kind, mirrored repos, ground-truth.yaml
  deploy/
    compose/
    kubernetes/
    keycloak/
    cerbos/
    temporal/
    docling/
    helm/
    litellm/
    observability/
  tests/
    security/
    integration/
    e2e/
    benchmarks/
    fixtures/
  openspec/                       # phase proposals, design, requirements, tasks
  docs/
```

## Conventions
- Boundary: feature modules communicate through typed services/domain events; no arbitrary import of repositories from unrelated modules.
- Each domain owns schema migrations and policies, and exposes versioned commands/queries.
- API response DTOs are independent from DB ORM objects and project data always carries tenant scope.
- HTTP uses RFC 9457-style errors, typed pagination, cursor and idempotency keys.
- Workers use `asyncio`, `TaskGroup` where appropriate, process pooling for CPU-bound parsers, bounded concurrency/queues and cooperative cancellation.
- Frontend uses query caching by scope and policy revision; one central project/environment/snapshot context drives all pages.
- Unit/integration/e2e tests run in CI; migrations, OpenAPI and OpenSpec spec validation checked in dedicated jobs.

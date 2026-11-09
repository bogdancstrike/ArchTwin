# Technologies — adopt, don't reinvent

ArchTwin's differentiation is the **evidence model, drift semantics and architect workflows**. Everything else is adopted from open-source projects with large communities, active maintenance and permissive or well-understood licenses. Before adding custom infrastructure code, check this table; deviations need an ADR (`docs/architecture/adr/`).

Selection criteria: (1) broad adoption and active maintainers (CNCF/LF/Apache/major vendor backing preferred), (2) self-hostable, (3) license compatible with open-core distribution, (4) already proven in Horizon where possible (shared know-how), (5) replaceable behind an interface.

## Runtime stack

| Concern | Adopted | Why / notes | Rejected or deferred |
|---|---|---|---|
| API | **FastAPI** + Uvicorn, Pydantic v2 | async, OpenAPI-first, Horizon-proven | Django (heavier ORM coupling) |
| ORM / migrations | **SQLAlchemy 2 async** + asyncpg, **Alembic** | mature, typed, RLS-friendly | — |
| System of record | **PostgreSQL** (pgvector image) | relational + JSONB + FTS + vectors + LISTEN/NOTIFY in one engine | Neo4j/Qdrant as *authority* (allowed later as rebuildable projections) |
| Durable jobs / schedules / approvals | **Temporal** | retries, timers, signals, visibility; Horizon-proven | Celery, arq, custom cron, Airflow |
| Events | **Transactional outbox** in PostgreSQL | exactly-once side effects without a broker | Kafka (ADR needed with measured volume), Debezium |
| Cache / rate limits | **Valkey** (Linux Foundation Redis fork) | BSD licence, drop-in | Redis (licence change) |
| Object storage | any **S3-compatible**; **SeaweedFS** in Compose | Apache-2.0, Horizon-proven | MinIO (licence and community-edition changes) |
| Authentication | **Keycloak** (OIDC + PKCE) | CNCF incubating, identity brokering, SCIM via extensions | homegrown auth |
| Authorization | **Cerbos** PDP + `cerbos` SDK + query-plan **SQLAlchemy adapter** | policy-as-code, list filtering, tests | OPA (fine, but Cerbos fits resource/action model and Horizon), OpenFGA |
| Feature flags | **OpenFeature** SDK + PostgreSQL provider | CNCF standard API; swap to flagd/Unleash later | building a proprietary flag API |
| Secrets (KEK) | **OpenBao** Transit (or cloud KMS); `cryptography` AES-GCM envelopes | LF fork of Vault, MPL-2.0 | own crypto |
| AI gateway | **LiteLLM** | single egress, aliases, budgets, provider switch | direct provider SDKs in business code |
| LLM observability / evals | **Langfuse** (+ optional **promptfoo** red-team) | traces, datasets, experiments | — |
| Models (v1) | OpenAI via LiteLLM: `gpt-6-luna` (default), `gpt-6-terra`, `gpt-6-sol` (user-selectable), `gpt-5.6-luna` (fallback), `text-embedding-3-large` | Horizon-aligned | — |
| Document parsing | **Docling** (+ python-magic, optional **ClamAV**) | LF AI & Data, layout/table aware | custom PDF parsing |
| Code analysis | **tree-sitter** + official grammar wheels (`tree-sitter-python`; no runtime grammar downloads), **Syft** (CycloneDX SBOM), OpenAPI/AsyncAPI parsers, Backstage `catalog-info.yaml` | multi-language, battle-tested | writing language parsers; full program analysis |
| Git providers | **githubkit**, **python-gitlab**, git CLI | typed / official-ish clients | — |
| Kubernetes | **kubernetes_asyncio** (list/watch) | official API model | — |
| Runtime call graph | **OpenTelemetry** Collector *servicegraph* connector → Prometheus; Jaeger/Tempo dependencies | reuse existing telemetry | own agents / eBPF |
| Kafka metadata | **confluent-kafka** AdminClient + Schema Registry client | librdkafka-based | consuming payloads |
| DB catalog | SQLAlchemy `inspect()` reflection | multi-dialect | custom catalog SQL per engine |
| Notifications | **Apprise** | 100+ targets (email, Slack, Teams, webhooks) | per-channel integrations |
| Live updates | SSE (`sse-starlette`) | simple, proxy-friendly | WebSockets (not needed) |
| Graph algorithms | **networkx** on bounded subgraphs; recursive CTEs in Postgres | — | custom algorithms |
| Exports | **Pandoc** (DOCX), **WeasyPrint** (PDF), Jinja2 templates | Horizon-proven | — |
| ADR format | **MADR** | widely used, adr-tools/Log4brains compatible | custom template |
| Signing / provenance | **Sigstore cosign**, in-toto, SARIF for CI results | industry standard | custom signatures |

## Diagrams

| Concern | Adopted | Notes |
|---|---|---|
| Visual design system for every generated diagram | **diagram-design** (MIT, github.com/cathrynlavery/diagram-design) | tokens, 40 visual types, focal rule, complexity budget, six connector rules, anti-patterns; vendored into `packages/diagram-design-system` with attribution and enforced by a linter (AT-DIAGRAM_STUDIO-005/006) |
| Interactive editor | **React Flow** (`@xyflow/react`) | same tokens/node components as exports |
| Layout & orthogonal routing | **elkjs** (Eclipse Layout Kernel) | `edgeRouting: ORTHOGONAL`, port constraints for fanned attach points |
| Interchange | **Mermaid** (export / user imports, `securityLevel: strict`), **Structurizr CLI** (DSL ⇄ JSON) | never write a DSL parser; Mermaid's renderer is not used for platform figures |
| PNG rendering | headless Chromium (Playwright) | — |

## Frontend

React 19, Vite, TypeScript, TanStack Router + Query, shadcn/ui + Tailwind v4, react-oidc-context, i18next, Monaco (DSL editing), orval/openapi-typescript (generated client), Vitest, Playwright, axe-core. Same stack as Horizon.

## Engineering platform

| Concern | Adopted |
|---|---|
| Python packaging | **uv** |
| Lint / types | **ruff**, **mypy** or pyright; oxlint/ESLint |
| Tests | pytest, pytest-asyncio, **testcontainers**, **Hypothesis** (property), **Schemathesis** (OpenAPI fuzzing), Playwright, **k6** (load), **Toxiproxy** (fault injection) |
| Supply chain | **Renovate**, **Trivy**, **Syft**, **gitleaks**, pip-audit, cosign |
| Observability | OpenTelemetry SDK, Prometheus, Grafana, Loki, Tempo/Jaeger, structlog |
| Deployment | Docker Compose (dev/pilot), **Helm** + **CloudNativePG** (production) |
| Reference fixture | **OpenTelemetry Demo** (Astronomy Shop) on **kind** — polyglot services, Kafka, Postgres, OTel, Helm |

## Explicitly evaluated and not adopted (for now)
- **Airbyte / Meltano / Singer** — move rows into warehouses; ArchTwin needs metadata with provenance.
- **Backstage as the core** — great catalog/portal; ArchTwin *imports* its catalog instead of replacing it (positioning).
- **LikeC4 / Structurizr as the core model** — excellent model-as-code tools; used as interchange formats, but ArchTwin needs temporal evidence semantics they don't model.
- **Kafka, Neo4j, Qdrant, OpenSearch** — each requires an ADR with measured need; PostgreSQL covers MVP volumes.

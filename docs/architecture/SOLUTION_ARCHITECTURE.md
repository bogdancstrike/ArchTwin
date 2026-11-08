# Solution Architecture — ArchTwin

## 1. Logical architecture
A **modular monolith** owns all authoritative business transactions in a single FastAPI API process; specialized asyncio worker processes and Temporal workflows run expensive/asynchronous work. PostgreSQL is the system of record. The architecture graph is initially canonical relational data + edge tables + JSONB snapshots; Neo4j and Qdrant are **optional projections** powered by the outbox, never competing authorities.

### Logical components
| Domain | Ownership | Inbound/outbound contract |
|---|---|---|
| Organizations & projects | tenancy, scope, environments | project API / domain events |
| IAM/Policy | OIDC validation, Cerbos policy and sharing grants | authorized commands/query predicates |
| Flag service | typed flag catalog, policies, kill switches | evaluation service + cached revision |
| Connectors | provider credentials, cursors, webhooks and reconciliation | adapter SDK, normalized observations |
| Inventory | code/static + runtime + data/messaging discovery | source observations/evidence |
| Architecture model | temporal systems, elements and relationships | canonical graph and baseline snapshots |
| Diagram Studio | view definitions/layouts, C4/sequence rendering | graph query -> versioned view |
| Documentation/ADRs | source-backed drafts, reviews, publication | versioned docs and decisions |
| Drift | desired/code/runtime three-way comparison | deterministic rules -> findings |
| Planning | initiative/milestone/task linkage | external work item sync + evidence |
| Intelligence | architecture Q&A, design options, what-if | scoped retrieval -> LiteLLM -> Langfuse |
| Notifications | project alerts, digests and integrations | outbox -> delivery attempts |
| Audit & operations | evidence, trace logs, exports and SLOs | immutable audit + telemetry |

### Deployment
- **UI**: static React/Vite bundle served by Nginx/Ingress with OIDC PKCE, short-lived tokens, CSP.
- **API**: multiple FastAPI/Uvicorn replicas behind ingress; no session state in process.
- **Workers**: asyncio connector scanners, parser workers, indexers, temporal activity workers. Queue concurrency bounded by org/project/provider.
- **Temporal**: durable scan/reconciliation and approval workflows. In early MVP, a PostgreSQL outbox worker may be sufficient for small workloads; Temporal is adopted for retries, long-running workflows and human waits.
- **PostgreSQL HA**: schemas for identity metadata, projects, source observations, architecture graph, plans, docs, drift, audit and outbox.
- **Redis**: transient dedupe, rate limiting, cached flag revisions and bounded queues. Redis is NOT authoritative for evidence or permissions.
- **S3/MinIO**: immutable source files and normalized parses; store per-org/project object references and checksums.
- **Keycloak + Cerbos**: OIDC IDP and independent policy decision point; denial on PDP unavailable for sensitive operations.
- **LiteLLM**: the only upstream model egress; initial OpenAI aliases and optional later vLLM deployments; **Langfuse** receives trace/cost metadata with redaction settings.
- **Optional projections**: Neo4j for deep graph traversal and Qdrant for semantic retrieval, both fully rebuildable from PostgreSQL evidence.

## 2. Architectural states — never merge these accidentally
| State | Source | Authority | Example |
|---|---|---|---|
| **Desired** | approved ADR / architecture baseline | architect-approved intent | service A SHOULD publish Kafka events |
| **Static** | repo scanner at commit SHA | what source code declares | Spring producer publishes `orders.v1` |
| **Observed** | runtime/Kafka/telemetry/K8s at time T | actual observed deployment | consumer B active in prod |
| **Planned** | roadmap and drafts | not yet implemented | broker migration on milestone M3 |
| **External issue** | Jira/Taiga reported status | work management state | story Done |
| **Inferred** | AI or heuristics | hypothesis until corroborated | suspected data flow via queue |

A finding must include relevant evidence and prove its classification. Missing observation due to stale/unreachable source is **UNKNOWN**, not absence.

## 3. Persistence and eventing
- SQLAlchemy async sessions use transaction-scoped service methods; no unrestricted generic repository API that bypasses permission checks.
- Each authoritative command inserts domain updates and an `outbox_event` in one PostgreSQL transaction.
- Async worker reads outbox with SKIP LOCKED, delivers idempotently; uses `{source_id, provider_event_id}` unique keys.
- Source fetch -> immutable raw snapshot -> normalization -> source observation -> canonical element link -> graph version -> drift evaluation -> notifications.
- Connector offsets/checkpoints are committed **after** durable storage, not before; reconcile upstream state periodically.
- Every source observation includes `source_version`, `observed_at`, `ingested_at`, `parser_version`, `hash` and freshness/confidence.

## 4. Graph semantics
See `docs/architecture/DATA_MODEL.md`. Use canonical typed nodes/edges with identity reconciliation rules and separate projections for source/code/runtime/plan/desired. Keep historical model versions and source evidence. Approved baselines cannot be silently overwritten by scans.

## 5. Performance and boundaries
- Query paths: filtering by organization/project/environment and Cerbos policy **before** graph retrieval, caching or LLM context construction.
- Long graph traversals use bounded depth, node cap and time budget; default 3 hops, max configured per role.
- Large scanned artifacts live outside relational rows; store content hashes and extracted text indexes with lifecycle policy.
- Use targeted incremental scans and nightly full reconciliation, not frequent complete repository scans.
- Treat cost as an SLO: LLM completion max tokens, concurrency and spend; connector and browser request budgets.
- Project-owned queues and fair admission prevent one large scan from starving others.

## 6. Security boundaries
Browser -> API has OIDC/JWT checks. API -> Cerbos is internal mTLS in production. API -> source adapter carries a signed *task context*, not browser raw credentials. Worker -> LiteLLM scoped internal key. External connector responses are untrusted. Langfuse telemetry must not leak raw private documents by default. See `docs/security/THREAT_MODEL.md`.

## 7. Major architectural decisions
- ADR-0001: modular monolith first.
- ADR-0002: PostgreSQL canonical architecture graph with rebuildable projections.
- ADR-0003: three-way drift and evidence model.
- ADR-0004: Keycloak + Cerbos and explicit project federation.
- ADR-0005: LiteLLM + Langfuse, OpenAI first, local inference later.
- ADR-0006: provider connectors default read-only, write-back only with approval.

## 8. Failure cases
| Failure | Expected behavior |
|---|---|
| GitLab/Jira/cluster unavailable | preserve last verified observation; mark stale; continue other projects |
| Webhook missed/out-of-order | idempotent handling + periodic reconcile + cursor checkpoint |
| Cerbos unavailable | fail closed for protected reads and writes; audited degraded mode |
| LiteLLM or OpenAI unavailable | architecture UI, drift and static rules continue; AI functions degrade clearly |
| Langfuse unavailable | bounded telemetry buffering or metadata loss policy; never block critical deterministic drift |
| Neo4j/Qdrant down | fallback to PostgreSQL core; projections rehydrate from snapshots/outbox |
| Large project bursts | provider/project rate limiting; backpressure; age-of-data SLO |
| False positive drift | human triage, time-scoped suppressions, evidence inspection and rule version rollbacks |
| User permission revoked | recheck on live access, jobs, cached results and saved answer re-opening |

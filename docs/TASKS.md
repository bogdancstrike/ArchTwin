# Implementation tracker

Living status of the implementation against `openspec/changes/phase-*/tasks.md`. Updated after every task.
Legend: ✅ done and verified (automated tests + live run) · 🟡 done, partially verified · 🚧 partial · ⏳ open · ⏭ deferred ([Later] in the spec)

Rule (AGENTS.md): checkboxes in the OpenSpec `tasks.md` files are ticked only once code is **merged with green CI**. Work lives on
branch `feat/walking-skeleton-m1` (CI: python, integration, policies, web, spec, secrets).

## Verification evidence (2026-11-09, local Compose stack + shop fixture)
| Suite | Command | Result |
|---|---|---|
| Unit (incl. fixture ground truth, webhook HMAC, Kafka detection, OTel/GitHub with mocked HTTP) | `make test` | 99 passed |
| RLS isolation (as `archtwin_app`) | `make test-integration` | 8 passed |
| API journeys on the live stack (+ `/home`, live fixture connectors, signed webhooks, live GitHub) | `make test-e2e` | 24 passed (GitHub live test skips when unauthenticated rate limit is exhausted) |
| Browser (PKCE login, home, C4 zoom, evidence, axe WCAG AA on home + projects) | `make test-ui` | 2 passed |
| Cerbos policy tests | `make policy-test` | 44 passed |
| OpenSpec | `make spec-validate` | 7/7 valid (strict) |
| Migrations | up → down → up | ok (CI job `integration`) |

**Live run against the shop fixture** (`make fixtures-up && make fixtures-demo`): 6 connectors (git, Docker, OTel service graph,
PostgreSQL, MySQL, Kafka) → one model where `kafka-topic:archtwin-fixtures/kafka/orders.created` carries both static (code) and runtime
(cluster) origins, `shop-web → shop-orders` is confirmed by OTel traffic, tables from both engines with sensitive columns flagged, and the
L2 view reads `shop-orders —publishes · orders.created→ kafka`, `shop-billing —consumes · orders.created→ kafka`.

**Live run against Horizon** (`/sources/horizon`, commit `f6a42fe`): 1,242 files → 1,493 observations, 98 documents; snapshot 442
elements / 1,034 relationships; 48/48 generated views lint clean. With Horizon stopped, the Docker connector produced exactly 18
`DR-RUNTIME-NOT-RUNNING` findings (one-shot jobs and optional profiles excluded); after `docker compose up` of Horizon all 18
auto-resolved and the 22 runtime containers reconciled with static keys (no fuzzy matching). Scanning the older commit `ecbf68e`
against the approved baseline produced 12 findings (unplanned `backup`/`demo-seed`, `docling` running but undeclared, planned
`ingest → docling` no longer observed). Assistant (`gpt-6-luna`, `gpt-6-sol` via LiteLLM, traced in Langfuse): grounded answers,
0 invalid citations; `gpt-6-terra` failed the provider capability probe and is hidden (spec: "hidden, not degraded").

## Phase 01 — foundation
| Task | Status | Notes |
|---|---|---|
| 0.1 Monorepo layout, uv, npm | ✅ | `apps/api` (uv, Python 3.13), `apps/web` (npm), `deploy/`, `packages/diagram-design-system` |
| 0.2 compose.yaml + healthchecks + Makefile | ✅ | `archtwin-*` core, `archtwin-thirdparty-*` adopted services; coexists with Horizon |
| 0.3 init-env.sh (only OPENAI_API_KEY user-supplied, fake mode) | ✅ | no key ⇒ `ARCHTWIN_LLM_MODE=fake` |
| 0.4 CI | 🟡 | ruff, pytest, migrations, RLS suite, Cerbos, web build, OpenSpec, gitleaks; nightly full-stack e2e. Trivy/Syft/Renovate ⏳ |
| 0.5 structlog + redaction, health endpoints | ✅ | OpenTelemetry traces ⏳ |
| 0.6 demo: `make up` → login → empty project list | ✅ | Playwright smoke |
| 1.1–1.4 RequestContext, UUIDv7, RFC 9457, Idempotency-Key, `SET LOCAL`, outbox + relay + receipts | ✅ | |
| 2.1 Keycloak realm, JWKS, 401 before DB | ✅ | |
| 2.2 Cerbos policies + tests | ✅ | 44 policy tests |
| 2.3 PlanResources → SQL (cerbos-sqlalchemy), unknown operator ⇒ deny | ✅ | unit-tested deny path |
| 2.4 envelope encryption, redaction, canary scan | ✅ | OpenBao adapter ⏭ |
| 2.5 job context carries principal | ⏭ | jobs run as system context; flags re-checked at job start |
| 3.1–3.3 tenancy tables, RLS, project API + wizard, isolation suite | ✅ | |
| 3.4–3.5 org deletion workflow, break-glass | ⏭ | |
| 4.1–4.4 flag catalog from docs, OpenFeature provider, immutable invariants, admin UI | ✅ | 5 s cache (< 15 s target) |
| 5.1–5.3 audit in same tx, hash chain, verify CLI, viewer | ✅ | `python -m archtwin.cli audit verify` |
| 6.1–6.3 UI shell, project home cards, axe check | ✅ | |
| 7.1 LiteLLM aliases + Langfuse | ✅ | |
| 7.2–7.3 AI gateway + fake mode, model picker, server-side validation | ✅ | capability probe hides unavailable models (per API process; Valkey-shared state ⏳) |
| 7.4 network isolation proving only LiteLLM reaches the provider | ⏳ | |

## Phase 02 — connectors
| Task | Status | Notes |
|---|---|---|
| 0.1–0.2 reference fixture | ✅ | `fixtures/shop` (separate Compose project `archtwin-fixtures`, containers `archtwin-fixture-*`): OTel-instrumented web/orders/inventory/billing + Kafka, Schema Registry, PostgreSQL, MySQL, collector servicegraph → Prometheus; `ground-truth.yaml`; `make fixtures-up/-demo/-down`. OTel Demo on kind ⏭ (Docker-only for now) |
| 1.1 SDK, manifest, registry, conformance | 🟡 | 8 kinds: git, github, docker, otel_servicegraph, postgresql, mysql, kafka, http_openapi; manifests carry category/scopes/webhooks; conformance kit ⏳ |
| 1.2 sealed credentials, test endpoint with scopes/warnings | ✅ | |
| 1.3 egress guard + SSRF suite | ✅ | DNS pinning ⏳ (resolve-and-check only) |
| 1.4 Temporal workflows, flags re-checked | ✅ | scheduled reconcile loop (flag `connectors.full_reconciliation`) |
| 1.5 webhook ingress | ✅ | `POST /api/v1/webhooks/{org}/{project}/{connector}`: GitHub `X-Hub-Signature-256` / generic HMAC + 5-min replay window, `webhook_deliveries` dedupe (migration 0003, RLS), one scan per commit, issue/PR events update the single work item; rejections opaque, metered, nothing stored (unit + live e2e). Prometheus export of the counters ⏳ |
| 1.6 partial scans never tombstone | ✅ | |
| 2.1–2.3 observations, freshness, conflicts | ✅ | monthly partitions ⏳ |
| 3.1 GitHub App / GitLab adapters | 🟡 | GitHub REST adapter: repo metadata, branches, code via the git analyzers at any ref, webhooks; verified live on `bogdancstrike/ArchTwin`. GitHub App auth + GitLab ⏳ |
| 3.2–3.4 declared artifacts, tree-sitter detectors, precision/recall | ✅ | + Kafka producer/consumer detection (confluent-kafka, kafka-python, aiokafka; literal topics only) keyed to the configured broker; recall 100% / no invented app edges on the fixture ground truth (CI); grammar from the official `tree-sitter-python` wheel (the language pack downloaded grammars at runtime — intermittent 504s silently dropped modules; now parse failures mark the scan partial). Syft SBOM ⏳ |
| 4.1–4.2 Kubernetes adapter, RBAC templates | ⏭ | deferred by the product owner (Docker-only for now); Docker Engine runtime adapter covers Compose hosts |
| 4.3 OTel service-graph adapter | ✅ | Prometheus HTTP API → runtime `calls`/`writes`/`publishes` edges with window, requests, errors, p95; `service_map`/`peer_map`; unknown peers reported, never invented; absence in traces is not coverage (live e2e on the fixture) |
| 5.1 PostgreSQL catalog | ✅ | + MySQL on the same SQLAlchemy reflection path (`sql_catalog`), READ ONLY transaction, privilege warnings (REFERENCES-only account passes) |
| 5.2 Kafka | ✅ | confluent-kafka AdminClient: topics/partitions/RF, consumer groups + members, lag from committed offsets vs watermarks (never joins a group, no payloads), Schema Registry subjects → `implements`; group→service only via `group_services` (or exact name, 0.7); static + runtime topic identities merge |
| 5.3 sensitive-column classifier | ✅ | |
| 6.1, 6.3 work connectors read-only | ✅ | GitHub issues + PRs as `work-item` (origin `issue`), closing keywords → `implements`; no write call exists (source test); write/admin scopes and push permissions warned at test time |
| 7.1–7.2 uploads + parsing | ✅ | magic bytes (binary rejected), docling-serve profile for PDF/DOCX |

## Phase 03 — architecture
| Task | Status | Notes |
|---|---|---|
| 1.1–1.5 graph, deterministic builder, identity merge/split, snapshots + diff + time travel, baselines (author ≠ approver) | ✅ | snapshot dedupe includes the coverage signature |
| 2.1 C4 context/container views, React Flow, elkjs in a Web Worker | ✅ | |
| 2.2 layout overrides survive regeneration, reset | ✅ | |
| 2.3 evidence panel | ✅ | |
| 2.4 snapshot comparison view | ✅ | |
| 2.5 Mermaid + Structurizr DSL export, XSS corpus | ✅ | |
| 2.8 accessible table view, keyboard | ✅ | 2k-element performance check ⏳ |
| 2.9–2.11 design-system tokens, ≤ 9 primary nodes, ≤ 2 focal, orthogonal router, 6-rule linter, SVG/HTML export | ✅ | PNG export ⏳ |
| 2.13 C4 zoom L1→L2 (+ L3 from import graphs) | ✅ | Playwright covers dblclick / Enter / Backspace; L2 rolls container→topic edges up to the broker labelled with the topic; one-shot jobs grouped and shown as completed |
| 3.1–3.2 MADR ADRs | ✅ | |
| 4.1–4.3 documentation engine | ✅ | PDF/DOCX ⏭ |
| 5.x architecture reviews | ⏭ | |

## Phase 04 — drift
| Task | Status | Notes |
|---|---|---|
| 1.1–1.4 rule catalog, three-way evaluator, stable IDs, accept/suppress | ✅ | truth table unit-tested |
| 2.1 debounced evaluation | ✅ | `GraphBuildWorkflow` (signal-with-start) → `DriftWorkflow` |
| 2.2 10k-webhook burst test | ⏳ | |
| 2.3 outage ⇒ UNKNOWN, no deletion drift | ✅ | |
| 3.1–3.2 triage, evidence view | ✅ | |
| 4.1 in-app notifications + SSE | ✅ | |
| 4.2 Apprise, 4.3 Prometheus/Grafana | ⏭ / ⏳ | |

## Phase 06 — intelligence (pulled forward)
| Item | Status | Notes |
|---|---|---|
| grounded assistant, citation validator | ✅ | |
| integration designer (2 options + Mermaid) | ✅ | |
| ADR drafting (proposed, AI-flagged) | ✅ | |
| federation, impact analysis, evals | ⏳ | |

## Cross-cutting — web experience
| Item | Status | Notes |
|---|---|---|
| Personal home `/home` (`GET /api/v1/home`) | ✅ | totals, needs-attention (pending baselines, proposed ADRs, high drift, stale sources), activity feed, project health cards; only Cerbos-visible projects, each read under its own RLS context; e2e `test_home.py` (outsider sees nothing) |
| Visual refresh | ✅ | self-hosted Geist / Instrument Serif, deep-ink sidebar with project avatars, project header + icon tabs, stat tiles, skeleton loaders, richer project overview (snapshot trend, evidence by origin, top drift, recent scans, latest ADRs), searchable/sortable projects; axe (WCAG 2 AA) clean on Home and Projects |

## Phases 05, 07
Specified, not started.

## Changelog
- 2026-11-09 — M1 data-source connectors (GitHub, MySQL, Kafka + Schema Registry, OTel service graph), webhook ingress, shop fixture with ground truth; analyzer fixes (services keyed by system/name, deterministic grammar loading).
- 2026-11-09 — `/home` dashboard + UI refresh (fonts, shell, overview, projects); axe AA clean.
- 2026-11-08 — walking skeleton + M1/M2 slice, web UI, full test pyramid, CI; live verification against Horizon (see above).

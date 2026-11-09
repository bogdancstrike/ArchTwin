<div align="center">

<img src="docs/assets/logo.svg" width="96" alt="ArchTwin logo" />

# ArchTwin

**The living digital twin of your software architecture.**
Know what was designed, what was planned, what the code says and what is actually running — and get told, with evidence, when they drift apart.

[![Status: MVP in progress](https://img.shields.io/badge/status-MVP%20in%20progress-eb6c36?style=flat-square)](#-roadmap--status)
[![OpenSpec](https://img.shields.io/badge/spec-OpenSpec-2d3142?style=flat-square)](openspec/)
[![Python FastAPI](https://img.shields.io/badge/API-FastAPI%20asyncio-009688?style=flat-square&logo=fastapi&logoColor=white)](docs/TECHNOLOGIES.md)
[![React](https://img.shields.io/badge/UI-React%20%2B%20React%20Flow-61DAFB?style=flat-square&logo=react&logoColor=black)](docs/TECHNOLOGIES.md)
[![PostgreSQL](https://img.shields.io/badge/store-PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)](docs/architecture/adr/0002-postgresql-canonical-store-and-outbox.md)
[![Temporal](https://img.shields.io/badge/workflows-Temporal-141414?style=flat-square)](docs/architecture/adr/0007-temporal-for-all-durable-work.md)
[![Keycloak + Cerbos](https://img.shields.io/badge/auth-Keycloak%20%2B%20Cerbos-4d4d4d?style=flat-square)](docs/architecture/adr/0004-keycloak-cerbos-and-federation.md)
[![LiteLLM + Langfuse](https://img.shields.io/badge/AI-LiteLLM%20%2B%20Langfuse-6E56CF?style=flat-square)](docs/ai/AI_ARCHITECTURE.md)

[What it is](#-what-it-is) · [Quick start](#-quick-start) · [Features](#-features) · [How it works](#-how-it-works) · [Architecture](#-architecture) · [Tech stack](#-tech-stack) · [Roadmap](#-roadmap--status) · [Docs](#-documentation) · [Contributing](#-contributing)

</div>

---

> [!NOTE]
> **Status:** phases 01–04 (MVP scope) and the grounded assistant from phase 06 are implemented on `main` and tested end to end
> (unit, RLS isolation, live-stack API journeys, Playwright + axe, Cerbos policy suite; whole-system coverage gate ≥ 90 %).
> Phases 05 and 07, Kubernetes and Jira are specified, not implemented. Live progress per task: [`docs/TASKS.md`](docs/TASKS.md).

## 🚀 Quick start

```bash
./scripts/init-env.sh sk-your-openai-key   # writes .env, generates every internal secret (omit the key for zero-token fake LLM mode)
make up                                     # docker compose up -d --build (first start migrates and seeds)
open http://localhost:3200                  # admin/admin · alice, bob, vera, mallory / archtwin
```

The fastest way to see every connector working is the reference fixture (a separate Compose project):

```bash
make fixtures-up      # OTel-instrumented shop: web, orders, inventory, billing + Kafka, Schema Registry, PostgreSQL, MySQL, Prometheus
make fixtures-demo    # creates "Shop (reference fixture)" with git, Docker, OTel, PostgreSQL, MySQL and Kafka connectors and scans them
```

Or by hand: **New project → Datasources → Add datasource** (a local directory, `github`, `gitlab`, `taiga`, `docker`,
`otel_servicegraph`, `postgresql`, `mysql`, `kafka`, `http_openapi`) → **Scan** → **Architecture** (C4 zoom: double-click / Enter, Backspace to go up) → **Settings → Propose
baseline** (a different user approves) → **Drift** → **Assistant**.

### Your own sources: local directories, GitLab, Taiga

```bash
# .env — then `make up`
ARCHTWIN_SOURCE_WORKSPACE=/home/me/workspace/myproduct     # absolute; mounted read-only at the SAME path
ARCHTWIN_EGRESS_ALLOW_PRIVATE_HOSTS=gitlab.internal,taiga.internal   # self-hosted providers on 10.x / 172.16-31.x / 192.168.x
ARCHTWIN_EGRESS_INSECURE_TLS_HOSTS=taiga.internal          # only if a host has a self-signed / wrong-CN certificate
```

- **Local directory** — *Browse…* opens a folder picker over the mounted roots. A single repository is scanned at any ref; a
  folder of repositories (e.g. `myproduct/backend`) scans each repository as its own system; set `content: docs` for
  documentation or architecture folders (every Markdown/text file, ADRs anywhere, Mermaid/PlantUML/Structurizr sources;
  PDF/DOCX with the `documents` profile). Add as many directories to one project as you like.
- **GitLab** — paste project URLs (`https://gitlab.internal/group/sub/project`) or whole `groups`; the dialog links to the
  token page pre-filled with `read_api` + `read_repository`. Commits, branches, issues and merge requests; push webhooks scan
  only the pushed project.
- **Taiga** — paste the board URL (`https://taiga.internal/project/<slug>/kanban`); anonymous for public projects, otherwise a
  read-only user's username + password (or a token). Epics, stories, tasks, issues and sprints become work items.

| Container | Role | Port |
|---|---|---|
| `archtwin-web` | React UI (nginx, CSP, `/api` proxy) | 3200 |
| `archtwin-api` | FastAPI modular monolith | 127.0.0.1:8200 |
| `archtwin-worker` | Temporal worker + outbox relay + reconcile loop | — |
| `archtwin-migrate`, `archtwin-seed` | Alembic migrations, pilot-org seed (one-shot) | — |
| `archtwin-thirdparty-postgres` | PostgreSQL + pgvector (system of record, RLS) | 127.0.0.1:5452 |
| `archtwin-thirdparty-keycloak` | OIDC (PKCE) | 8280 |
| `archtwin-thirdparty-cerbos` | authorization PDP | — |
| `archtwin-thirdparty-temporal`, `-temporal-ui` | durable jobs | 127.0.0.1:8253 |
| `archtwin-thirdparty-litellm` | the only AI egress (gpt-6-luna / terra / sol) | 127.0.0.1:4200 |
| `archtwin-thirdparty-langfuse-web`, `-worker`, `-clickhouse` | LLM traces | 127.0.0.1:3201 |
| `archtwin-thirdparty-valkey`, `-seaweedfs` | cache / S3 object store | — |
| `archtwin-thirdparty-docker-proxy` | read-only Docker API for runtime discovery | — |
| `archtwin-thirdparty-docling` | PDF/DOCX parsing (profile `documents`) | — |

Tests: `make test` (unit) · `make test-integration` (RLS) · `make test-e2e` (API journeys on the live stack) · `make test-ui` (Playwright + axe) ·
`make policy-test` (Cerbos) · `make spec-validate` (OpenSpec) · `make coverage` (all suites with the API and worker instrumented; fails under 90 %).

## ✨ What it is

Architecture documentation rots the day it is written. Diagrams, ADRs, tickets, code and the running system all evolve separately, and architects find out about drift in production.

ArchTwin closes the **architectural continuity loop**:

```
Design → ADR → plan → code → runtime observation → drift → review → updated architecture
```

- 🔎 It **discovers** systems, services, modules, APIs, durable workflows, message channels, topics, databases, tables and workloads from your repositories, Docker hosts, PostgreSQL/MySQL, Kafka, OpenTelemetry, GitLab/GitHub/Taiga and your documents — read-only.
- 🧾 Every fact carries **evidence**: where it came from, which revision, when it was observed, how confident we are. Missing data is shown as **unknown**, never as "deleted".
- 🗺 It renders **C4 diagrams** (context → containers → components → code) and **sequence diagrams of every recognized flow**, generates complete **documentation**, and explains distributed services and modular monoliths alike.
- 🚨 It **detects drift** deterministically — against the approved baseline, against the **conformance rules of accepted ADRs**, against declared module boundaries, and between code and the running system.
- 🤖 It answers questions like **"How do I connect platform A and B?"** with cited options, trade-offs, diagrams and an ADR draft — without ever changing anything on its own.

Nothing is tuned to one application: every detector works on framework-level patterns (FastAPI, Spring, Temporal, Postgres LISTEN/NOTIFY, Redis, Kafka, MCP, Compose…). Two real platforms are used as benchmarks — a Python, workflow-driven agent platform (13 Temporal workflows, LISTEN/NOTIFY streaming, an MCP gateway) and a Java Spring Modulith messaging backend (11 modules, application events, Valkey pub/sub) — and ArchTwin reproduces their own architecture documents from code alone.

## 🧩 Features

### Projects, security and governance
- **Independent projects** with their own people, environments, connectors, baselines and AI budget.
- **Keycloak** single sign-on, **Cerbos** policy-as-code on every read and write (list filtering included), PostgreSQL **row-level security** as defence in depth.
- **Hash-chained audit log** with a verifier; envelope-encrypted connector secrets that never reach browsers, logs or prompts.
- **Feature flags** for every optional module, connector and AI operation — security invariants are never flaggable.
- **Roles & permissions**, **audit search**, **System** page (source roots, health), **Usage & costs** with spend limits.
- **Command palette (⌘K / Ctrl+K)**: jump anywhere, switch project, run actions, search elements, flows, decisions and documents. **Night mode** with neutral graphite surfaces and WCAG AA text.

### Discovery: deep code understanding
- **Connectors**: local directories (single repos, repository sub-folders at any commit, folders of repositories, documentation folders), Git over HTTPS, **GitHub**, **GitLab**, **Taiga**, **Docker** runtime, **OpenTelemetry** service graph, **PostgreSQL/MySQL** catalogs, **Kafka + Schema Registry**, live **OpenAPI**, uploaded documents (Docling). Signed webhooks; partial scans never cause false deletions.
- **Python** (tree-sitter): FastAPI/Flask/Starlette routes with router prefixes, component and module graphs per running service (entrypoints and CLI sub-commands resolved — including argparse dispatch branches), C4 L4 classes and functions, outgoing HTTP calls, Kafka producers/consumers, SDK resources, **Temporal workflows and activities** (who starts them, which worker executes them, what their activities do), **PostgreSQL LISTEN/NOTIFY channels** (including helper wrappers and channel-name factories), **MCP servers and tools**, DB schemas from SQL, Alembic (including raw DDL in `op.execute`), SQLAlchemy and Django.
- **Java / Spring** (tree-sitter): **Spring Modulith** modules (display names, named interfaces, allowed dependencies), module dependency graph with **boundary violations** and **cycles**, Spring MVC / WebFlux / JAX-RS endpoints, websocket handlers, `@Scheduled` jobs, **application events** with their listeners, Kafka / Rabbit / JMS listeners and producers, **Redis pub/sub and streams** with channel patterns (`"mail:" + id` → `mail:*`), per-method effects followed through injected collaborators (SQL tables read and written, events, channels, object storage), JPA entities, Flyway migrations.
- **TypeScript / web**: module folders and their dependencies, SPA → API calls matched to endpoints, RPC-style UIs (action literals, constant maps) end to end *UI → presenter → gate → backend*.
- **Deployment evidence** for precision: Compose networks (containers that share no network cannot talk), shared environment blocks (a service handed an address it never reads does not use it), LLM SDKs pointed at a gateway (calls go to the gateway, not the SaaS), credentials, bare-host variables, health-check probes, migration jobs owning the schema.
- Declared artifacts: OpenAPI, AsyncAPI, Dockerfiles, Compose (extends, profiles, sibling build contexts), Backstage `catalog-info.yaml`, CODEOWNERS, ADRs, Mermaid/PlantUML/Structurizr sources.

### Living architecture
- One canonical, **temporal** architecture graph: time-travel to any date, diff any two snapshots.
- **Guided baselines**: the Drift and Architecture pages explain the baseline and set it in one step — *use the current architecture as baseline*, *approve*, or *update the baseline to v8* — four-eyes for everyone, an audited self-approval exception for organization admins.
- **Diagram studio**: C4 context / container / component / code views with an animated zoom, durable workflows and channels rolled up onto their hosts (`api —starts MissionWorkflow→ temporal`), manual layout that survives regeneration, Mermaid and Structurizr export, the [diagram-design](https://github.com/cathrynlavery/diagram-design) system and a linter.
- **Flows**, recognized automatically and drawn as sequence diagrams with evidence per step:
  - **entry-point flows** for every endpoint, websocket, scheduled job and event listener — what the handler itself does (not every import of its module): stores written, workflows started, channels notified, gateways and MCP servers called;
  - **workflow flows**: starter → workflow → worker → activities' effects → listeners → child workflows;
  - **event flows**: in-process application events cascading into their listeners and their effects; NOTIFY / Redis channels delivered to the replicas and the streaming endpoints that forward them to clients;
  - request walks between containers and data-store flows.
- **ADRs** (MADR) with independent approval, immutable history and optional **conformance rules**.

### Documentation
- **Deterministic, exhaustive documents**: system overview (C4 diagrams, functional areas, **asynchronous and durable interactions**, **module structure** with dependency diagrams, violations and cycles, technology inventory), container catalog, interface catalog, data model (ER diagram), flows, testing guide, developer reference and decision log. Every sentence cites evidence; hand-written sections survive regeneration.
- **AI-drafted documents** — user manual, PRD, ARF (arc42) and developer guide — written section by section from a full outline with focused, cited evidence and a pre-flight cost estimate.
- **Exports** from Architecture, Flows, Drift, Decisions and Docs: Markdown, Word, PDF or a ZIP bundle with a provenance manifest.

### Drift and conformance
- **Three-way drift**: approved baseline vs code vs runtime, with `unknown` / `incomplete` when evidence is missing or stale.
- **Decisions as checkable architecture**: accepted ADRs can carry rules — `forbid` (X must not depend on Y), `require`, `only-via` (*the LLM provider only through the gateway*), `technology` — evaluated deterministically; a violation is a high-severity finding that cites the decision. Rules can be amended after acceptance by approvers (new audited version).
- **Module boundaries**: a module using another module's internals, a dependency outside `allowedDependencies`, or a cycle between modules.
- **Contract drift across services**: a UI action its gateway does not route, a gateway route to an endpoint the backend does not expose.
- **Signal, not noise**: re-analysing an unchanged commit is never drift; a new element is one finding (with its connections), not one per edge; health checks, volumes and one-shot jobs are ignored; a stopped system is one finding.
- Triage (assign, comment, suppress with expiry, accept as intended), delete false positives (never resurrected), in-app notifications over SSE.

### Grounded AI
- Architecture assistant over **scoped evidence only**, with citations validated against an evidence pack; unsupported claims are marked.
- **Per-task model routing** through LiteLLM ([`MODEL_PROFILES.yaml`](docs/ai/MODEL_PROFILES.yaml)), cost estimates before every call, a usage ledger and spend limits.
- **Ask a page** (Flows, Decisions, Docs): search first at no cost, then a short cited answer cached for identical questions.
- **Integration designer** for "connect A and B": options, trade-offs, diagrams and an ADR draft.
- Proposals only: nothing is applied, written to a tracker or deployed without explicit, authorized approval.

### Planned (specified, not yet implemented)
Kubernetes and Jira connectors, Syft SBOMs, Apprise notifications (email/Slack/Teams), Prometheus metrics and Grafana dashboards, the delivery phase (initiative → issue → PR → deployment traceability, CI checks as SARIF), cross-project federation and blast-radius analysis, and enterprise operations (Helm, CloudNativePG, SLOs). Progress per task: [`docs/TASKS.md`](docs/TASKS.md).

## 🔄 How it works

<p align="center"><img src="docs/diagrams/how-it-works.png" alt="How ArchTwin works: read-only sources become immutable observations, which build a temporal architecture graph; a deterministic drift engine compares it with the approved baseline, and diagrams, triage and grounded AI proposals are derived from it"></p>

## 🏗 Architecture

A **modular monolith** (FastAPI) plus **Temporal** workers from the same image, with **PostgreSQL** as the only system of record. Everything else is adopted open source.

<p align="center"><img src="docs/diagrams/containers.png" alt="ArchTwin containers: Web UI, FastAPI API, Keycloak and Cerbos, Temporal workers, PostgreSQL, object store, LiteLLM and read-only sources"></p>

<sub>More views: <a href="docs/diagrams/system-context.png">C4 system context</a> · <a href="docs/diagrams/drift-sequence.png">drift detection sequence</a> · <a href="docs/diagrams/ai-design-sequence.png">grounded AI sequence</a>. All diagrams are built with the <a href="https://github.com/cathrynlavery/diagram-design">diagram-design</a> system — sources in <a href="docs/diagrams/"><code>docs/diagrams/</code></a>.</sub>

Key decisions are recorded as ADRs in [`docs/architecture/adr`](docs/architecture/adr/README.md): modular monolith, PostgreSQL + outbox (no Kafka in MVP), three-way evidence model, Keycloak + Cerbos, LiteLLM with selectable models, read-only connectors, Temporal, OpenFeature flags, the diagram-design system with C4 zoom, and *adopt open source before building*.

## 🧰 Tech stack

| Layer | Choices |
|---|---|
| Backend | Python, FastAPI (asyncio), Pydantic v2, SQLAlchemy 2 async, Alembic |
| Data | PostgreSQL (graph tables, JSONB, FTS, pgvector), Valkey, S3-compatible storage (SeaweedFS) |
| Workflows | Temporal, transactional outbox |
| Identity & policy | Keycloak (OIDC + PKCE), Cerbos, OpenFeature, OpenBao (optional KMS) |
| Discovery | tree-sitter (Python, Java), GitHub/GitLab/Taiga REST, Docker Engine API, confluent-kafka, SQLAlchemy reflection, Docling, OpenTelemetry service graph (Prometheus) |
| Frontend | React 19, Vite, TypeScript, TanStack, shadcn/ui, Tailwind, React Flow, elkjs, Motion |
| Diagrams | diagram-design system, Mermaid & Structurizr (interchange) |
| AI | LiteLLM, Langfuse, OpenAI (`gpt-6-luna` default, `gpt-6-terra`, `gpt-6-sol`) |
| Ops | Docker Compose (Helm, CloudNativePG, Prometheus/Grafana planned) |

Full adopt-vs-build reasoning: [`docs/TECHNOLOGIES.md`](docs/TECHNOLOGIES.md).

## 🗺 Roadmap & status

| Phase | Increment | Milestone | Status |
|---|---|---|---|
| [01](openspec/changes/phase-01-foundation/) | Secure multi-project foundations (walking skeleton) | M1 | ✅ MVP implemented (OTel tracing, OpenBao, org deletion, break-glass: later) |
| [02](openspec/changes/phase-02-connectors/) | Discovery and connected evidence | M1 | 🚧 mostly: local directories + Git, GitHub, GitLab, Taiga, Docker runtime, OTel service graph, PostgreSQL/MySQL, Kafka + Schema Registry, live OpenAPI, uploads, signed webhooks; deep Python and Java/Spring analysis (workflows, channels, events, modules); Kubernetes (deferred: Docker-only for now), Jira, Syft SBOM open |
| [03](openspec/changes/phase-03-architecture/) | Living diagrams, C4 zoom, docs and ADRs | M1 | ✅ MVP implemented: graph, snapshots, guided baselines, C4 L1–L4 zoom, recognized flows as sequence diagrams, linter, exports (Markdown, DOCX, PDF, ZIP), ADRs with conformance rules, complete generated docs (architecture reviews: later) |
| [04](openspec/changes/phase-04-drift/) | Continuous drift and alerts | M2 | ✅ MVP implemented: three-way drift, ADR conformance, module boundaries and cycles, contract drift, noise controls, triage, suppressions, in-app/SSE notifications (Apprise, metrics: later) |
| [05](openspec/changes/phase-05-delivery/) | Plans, traceability and CI checks | M2 | 📝 specified |
| [06](openspec/changes/phase-06-intelligence/) | Grounded AI and cross-platform design | M3 | 🚧 assistant, integration designer, ADR drafting, model picker implemented (federation, impact analysis, evals: later) |
| [07](openspec/changes/phase-07-enterprise/) | Enterprise operations and extensibility | M4 | 📝 specified |

Delivery is risk-first: walking skeleton, time-boxed spikes with go/no-go criteria, then thin vertical slices against reference fixtures (the `fixtures/shop` Compose project with ground truth) and two real benchmark platforms (Python and Java). See the [implementation plan](docs/IMPLEMENTATION_PLAN.md).

## 📚 Documentation

| | |
|---|---|
| [Docs index](docs/README.md) | Everything in one place |
| [PRD](docs/PRD.md) | Problem, personas, workflows, non-goals |
| [Solution architecture](docs/architecture/SOLUTION_ARCHITECTURE.md) | Containers, states, persistence, failure behaviour |
| [Implementation plan](docs/IMPLEMENTATION_PLAN.md) | Milestones, spikes, risks, rollback |
| [Threat model](docs/security/THREAT_MODEL.md) | Trust boundaries and controls |
| [AI architecture](docs/ai/AI_ARCHITECTURE.md) | Grounding, model selection, evaluation |
| [Spec index](docs/SPEC_INDEX.md) | All 38 capabilities and requirements |

### Working with the specs

```bash
npm install -g @fission-ai/openspec
openspec list
openspec validate --all --strict --no-interactive
openspec show phase-01-foundation
```

## 🤝 Contributing

Contributions are welcome — ArchTwin is spec-driven, so start with an issue or an OpenSpec change proposal. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for the workflow and [`AGENTS.md`](AGENTS.md) for the engineering rules that humans and coding agents follow.

## 🙏 Acknowledgements

ArchTwin stands on great open source: Keycloak, Cerbos, Temporal, PostgreSQL, LiteLLM, Langfuse, Docling, tree-sitter, React Flow, elkjs, OpenTelemetry, Structurizr, Mermaid and the [diagram-design](https://github.com/cathrynlavery/diagram-design) system. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## 📄 License

No license has been chosen yet. Until one is added, all rights are reserved by the author.

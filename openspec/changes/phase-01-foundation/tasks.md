# Implementation tasks — phase-01-foundation

Legend: **[MVP]** required for milestone M1 · **[Later]** may slip to a later phase without blocking M1.
Rule: a task is checked only when code is merged, tests are green in CI, and the linked requirement scenarios pass.

## 0. Walking skeleton and engineering platform (week 1–2)
- [x] 0.1 [MVP] Monorepo layout per `docs/ops/REPO_LAYOUT.md`; `uv` workspace for Python, `npm` for web; `.python-version` pinned after confirming wheels for Docling, tree-sitter and confluent-kafka.
- [x] 0.2 [MVP] `compose.yaml` with postgres(pgvector), keycloak (realm import), cerbos (policy mount), temporal + ui, valkey, seaweedfs, litellm, langfuse, api, worker, web; healthchecks on every service; `make up`, `make down`, `make logs`, `make test`.
- [x] 0.3 [MVP] `scripts/init-env.sh` generates every internal secret into `.env`; only `OPENAI_API_KEY` is supplied by the user; `ARCHTWIN_LLM_MODE=fake` supported.
- [ ] 0.4 [MVP] CI (GitHub Actions): ruff, mypy/pyright, pytest (unit + testcontainers integration), vitest, oxlint/eslint, Playwright smoke, `openspec validate --all --strict`, Alembic up/down/up, gitleaks, Trivy image scan, Syft SBOM, Renovate config.
- [ ] 0.5 [MVP] Observability baseline: structlog JSON logs with secret redaction, OpenTelemetry traces (FastAPI, SQLAlchemy, httpx), `/health/live` and `/health/ready`.
- [x] 0.6 [MVP] Demo: `make up` on a clean machine → login as demo admin → empty project list. Record in `docs/acceptance/end-to-end-journeys.md`.

## 1. Kernel: request context, errors, IDs, outbox — AT-CANONICAL_EVENTS-001..003
- [x] 1.1 [MVP] `RequestContext`, UUIDv7 IDs, RFC 9457 errors, cursor pagination, `Idempotency-Key` middleware (stored responses in Postgres, 24h TTL).
- [x] 1.2 [MVP] SQLAlchemy async session-per-request with `SET LOCAL app.*`; repository base class requires `RequestContext`.
- [x] 1.3 [MVP] `outbox_events` table + relay (SKIP LOCKED, LISTEN/NOTIFY wake-up, exponential backoff, dead-letter status) + consumer idempotency table `(consumer, event_id)`.
- [x] 1.4 [MVP] Tests: rollback emits no event; crash between handler and ack applies once; out-of-order revision ignored; snapshot rows immutable (trigger).

## 2. Identity and authorization — AT-IDENTITY_POLICY-001..005
- [x] 2.1 [MVP] Keycloak realm export (roles, PKCE client, demo users); JWT validation with JWKS cache + rotation; 401 before DB access.
- [x] 2.2 [MVP] Cerbos policies for org, project, environment, member, flag, audit (`deploy/cerbos/`); policy tests with `cerbos compile` + test suites in CI.
- [ ] 2.3 [MVP] Cerbos `PlanResources` → SQLAlchemy via the official adapter; unsupported operator ⇒ deny; fuzz/property tests on plan shapes.
- [ ] 2.4 [MVP] Envelope encryption service + `KeyProvider` (file KEK dev; OpenBao Transit adapter); redaction on read; canary-secret CI scan of logs/traces/responses.
- [ ] 2.5 [Later] Job context carries principal + policy revision; worker re-authorizes before sensitive reads/writes (needed by phase 02, implement with first connector job).

## 3. Organizations and projects — AT-ORGANIZATIONS-001..003, AT-PROJECT_BOUNDARIES-001..004
- [x] 3.1 [MVP] Org/project/environment/membership tables with composite FKs `(org_id, project_id)` and RLS policies.
- [x] 3.2 [MVP] APIs + UI wizard: create project (title, purpose, owners, environments, tags); last-owner protection.
- [x] 3.3 [MVP] Isolation suite: user A cannot read/list/count B in API, search stub, cache keys, jobs; client-supplied `org_id` ignored.
- [ ] 3.4 [Later] Org deletion/export workflow as a Temporal workflow with approval step and retention checks.
- [ ] 3.5 [Later] Break-glass grants with expiry and audit.

## 4. Feature flags — AT-FEATURE_FLAGS-001..003
- [x] 4.1 [MVP] Typed catalog (`flags/catalog.yaml`) generated from `docs/feature-flags/FLAG_CATALOG.md`; CI fails if code references an unregistered key.
- [x] 4.2 [MVP] OpenFeature provider backed by Postgres overrides; precedence rules; LISTEN/NOTIFY invalidation (<15 s propagation target, measured).
- [x] 4.3 [MVP] Security invariants hard-coded ON; attempts to change them rejected and audited.
- [x] 4.4 [MVP] Admin UI: list flags, scope overrides, audit history. `require_flag()` dependency for API + worker helper for queued jobs.

## 5. Audit — AT-AUDIT_PROVENANCE-001..003
- [x] 5.1 [MVP] Audit envelope written in the same transaction as the action (allow and deny decisions, Cerbos decision ID, trace ID).
- [x] 5.2 [MVP] Hash chain per org, trigger blocking UPDATE/DELETE, privileges revoked; `archtwin audit export|verify` CLI; tamper/gap tests.
- [x] 5.3 [MVP] Audit viewer in UI (filter by actor, project, action).

## 6. UI workspaces — AT-UI_WORKSPACES-001..003
- [x] 6.1 [MVP] Shell: login, org/project/environment switcher (single context store), light/dark themes, keyboard navigation, read-only states.
- [x] 6.2 [MVP] Project home with placeholder cards (health, drift, decisions, freshness) fed by real endpoints that return "not configured".
- [x] 6.3 [MVP] axe-core Playwright check on core pages (WCAG 2.2 AA target).

## 7. LLM gateway (infrastructure only) — AT-LLM_GATEWAY-001..005
- [x] 7.1 [MVP] LiteLLM config with Horizon-aligned aliases: `gpt-6-luna` (default), `gpt-6-terra`, `gpt-6-sol` (selectable), `gpt-5.6-luna` (fallback), `text-embedding-3-large`; Langfuse callback; `num_retries` at exactly one layer.
- [x] 7.2 [Later] `AiGateway` interface + fake implementation; admin-only diagnostics endpoint behind `module.llm-gateway`.
- [x] 7.3 [Later] Model selection: `GET /api/v1/ai/models` (registered ∩ capability-validated ∩ org/project allowlist), user preference + per-request override, server-side validation, alias recorded on PromptRun/Langfuse; model picker component in the UI (default Luna). UI is wired in phase 06 with the first AI feature.
- [ ] 7.4 [Later] NetworkPolicy/compose network isolation proving only LiteLLM can reach the provider.

## X. Phase exit gates
- [ ] X.1 Threat review against `docs/security/THREAT_MODEL.md`; default-deny verified.
- [ ] X.2 Isolation, audit-tamper and flag-bypass suites green in CI.
- [ ] X.3 Latency baseline recorded for project/list endpoints with RLS and Cerbos enabled.
- [ ] X.4 Rollback rehearsal: deploy N, then N-1, data still readable.

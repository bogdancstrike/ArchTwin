# Design: Secure multi-project foundations

## Context
This increment implements the requirements in `specs/`. Platform architecture: `docs/architecture/SOLUTION_ARCHITECTURE.md`; data semantics: `docs/architecture/DATA_MODEL.md`; threats: `docs/security/THREAT_MODEL.md`; technology choices: `docs/TECHNOLOGIES.md`; decisions: `docs/architecture/adr/`.

Goal: a **walking skeleton** with production-grade security boundaries, but minimal features. Everything later phases need (request context, authorization, outbox, flags, audit, Temporal) exists and is tested before any connector is written.

## Goals / Non-goals
- **Goals:** tenancy model, OIDC login, Cerbos authorization incl. list filtering, transactional outbox, hash-chained audit, typed flags, envelope-encrypted secrets, UI shell, LiteLLM/Langfuse deployed with an admin smoke test.
- **Non-goals:** connectors, graph, diagrams, user-facing AI, SCIM provisioning, multi-region, HA.

## Decisions

| # | Decision | Adopted OSS | Why not build / alternatives |
|---|---|---|---|
| D1 | One backend image, two entrypoints: `api` (FastAPI/Uvicorn) and `worker` (Temporal worker + outbox relay) | FastAPI, Uvicorn, Temporal Python SDK | Microservices rejected (ADR-0001). Celery/arq rejected: Temporal gives retries, schedules, human waits and visibility in one tool already operated in Horizon |
| D2 | Authentication via Keycloak OIDC Auth Code + PKCE; API validates JWT (issuer, audience, exp, JWKS rotation) | Keycloak, PyJWT `PyJWKClient`, react-oidc-context / oidc-client-ts | Homegrown auth forbidden. Realm export committed under `deploy/keycloak/` for reproducible dev |
| D3 | Authorization via Cerbos: `CheckResources` for commands/single reads; `PlanResources` → SQL for lists | Cerbos PDP, `cerbos` SDK, Cerbos query-plan **SQLAlchemy adapter** | Writing a policy engine or AST translator from scratch is high-risk. The adapter raises on unsupported operators → we map that to **deny** (fail closed) |
| D4 | Memberships and role bindings live in PostgreSQL (authoritative); Keycloak only proves identity | — | Keycloak groups cannot express per-project roles with expiry and audit cleanly |
| D5 | `RequestContext(principal, org_id, project_id?, env_id?, policy_revision, trace_id)` created once per request/job; repositories require it as a parameter | — | Makes "query without scope" a type error rather than a review finding |
| D6 | RLS as **defense in depth**: `SET LOCAL app.org_id/app.project_id` inside each transaction; policies on every scoped table | PostgreSQL RLS | `SET LOCAL` is transaction-scoped, so pooled connections cannot leak a stale tenant |
| D7 | Transactional outbox: domain write + `outbox_events` row in one transaction; relay uses `FOR UPDATE SKIP LOCKED`, woken by `LISTEN/NOTIFY`, dispatches to in-process handlers or starts Temporal workflows | PostgreSQL | Kafka not needed at MVP volumes (ADR-0002). Debezium considered only if Kafka is later adopted |
| D8 | Feature flags: catalog defined in code (`flags/catalog.yaml`, typed), overrides in PostgreSQL, evaluation through **OpenFeature** API with a custom PostgreSQL provider; cache invalidated via `LISTEN/NOTIFY` | OpenFeature Python SDK | Vendor-neutral API; can swap to flagd/Unleash later without touching call sites. Precedence: emergency-off > org policy > project/env > role cohort > default |
| D9 | Audit: append-only `audit_events` with `hash = sha256(prev_hash ‖ canonical_json(event))` per org chain; UPDATE/DELETE revoked from app role and blocked by trigger; `archtwin audit verify` CLI | PostgreSQL, `cryptography` | No mature OSS app-level tamper-evident audit log fits in-process; this is ~200 lines and fully testable. Optional later: anchor chain heads with Sigstore Rekor |
| D10 | Secrets: envelope encryption (AES-256-GCM DEK per secret, KEK from a `KeyProvider`): local file KEK in dev, **OpenBao/Vault Transit** or cloud KMS in prod | `cryptography`, OpenBao (optional) | Never roll our own crypto primitives; only the envelope wiring is ours |
| D11 | Migrations with Alembic, expand/contract only; CI runs upgrade → downgrade → upgrade on an empty and a seeded DB | Alembic | — |
| D12 | LiteLLM + Langfuse deployed in Compose; only LiteLLM holds `OPENAI_API_KEY`; `ARCHTWIN_LLM_MODE=fake` for CI | LiteLLM, Langfuse, `openai` SDK pointed at LiteLLM | Same pattern as Horizon; zero-token CI |
| D13 | Errors as RFC 9457 problem+json; cursor pagination; `Idempotency-Key` on POST commands; `If-Match` revisions on updates | FastAPI | — |
| D14 | UI shell: React 19 + Vite + TypeScript + TanStack Router/Query + shadcn/ui + Tailwind v4; API client generated from OpenAPI | orval or openapi-typescript | Same stack as Horizon → shared know-how and components |

## Data ownership
`orgs` owns organizations and org settings; `projects` owns projects/environments/memberships; `iam` owns role bindings and Cerbos policy versions; `flags` owns overrides/revisions; `audit` owns audit events; `kernel` owns outbox. Modules talk via service interfaces and domain events, never through each other's tables.

## Request flow
```
Browser (PKCE) → nginx → FastAPI
  → verify JWT (JWKS cache, rotation)          → 401 on failure, before any DB access
  → load principal + memberships (Postgres)     → RequestContext
  → flag check (module enabled?)                 → 404/feature-disabled
  → Cerbos CheckResources / PlanResources        → 403 or SQL filter (unknown operator ⇒ deny)
  → service method in one transaction: SET LOCAL tenant → domain write → audit event → outbox row
  → commit → NOTIFY outbox → relay → handlers/Temporal
```

## Threat controls (summary)
| Threat | Control | Test |
|---|---|---|
| IDOR across orgs/projects | context-derived scope, Cerbos, RLS, composite FKs `(org_id, project_id)` | property test enumerating foreign IDs returns 404 with no timing/count leak |
| Stale tenant on pooled connection | `SET LOCAL` per transaction; RLS default deny when unset | test reusing a connection across tenants |
| Policy adapter drops a filter | adapter exception ⇒ deny; fuzz test of plan ASTs | unknown operator test |
| Secrets in logs/traces | structlog redaction processor; canary secret scan in CI | canary test (AT-IDENTITY_POLICY-004) |
| Audit tampering | hash chain + trigger + revoked privileges | tamper test (AT-AUDIT_PROVENANCE-003) |
| Flag bypass | server-side + worker-side checks | direct API call with flag off |

## Failure behavior
PDP down ⇒ fail closed (503, retriable). Keycloak down ⇒ existing valid tokens keep working until expiry; new logins fail. Temporal down ⇒ commands still commit; outbox accumulates and drains later. LiteLLM/Langfuse down ⇒ no impact on any phase-01 journey.

## Risks / trade-offs
| Risk | Mitigation |
|---|---|
| Cerbos query-plan adapter doesn't cover a needed operator | Spike S1 in week 1 (see `docs/IMPLEMENTATION_PLAN.md`); fall back to "allowed-ID list" filter for that resource type |
| Temporal adds operational weight early | Uses the same Postgres; single dev container (`temporalio/auto-setup`); proven in Horizon |
| Over-building governance (break-glass, org deletion) before value | Marked *deferrable* in tasks; only "last owner" and audit are MVP |
| RLS performance/complexity | RLS is defense in depth only; benchmark list endpoints in CI with RLS on |

## Rollback
Each module ships dark (flag OFF where flaggable). Migrations are expand-only within the phase. Rollback = previous image; audit and outbox tables are append-only and remain compatible.

## Open questions
- Single Keycloak realm with org claim vs realm-per-org? **Default:** single realm, org membership in Postgres; revisit for customers needing separate IdPs (Keycloak identity brokering covers that).
- Which KMS for first pilot (OpenBao vs cloud KMS)? Decided per pilot; `KeyProvider` interface hides it.

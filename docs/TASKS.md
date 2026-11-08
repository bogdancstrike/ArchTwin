# Implementation tracker

Living status of the implementation against `openspec/changes/phase-*/tasks.md`. Updated after every task.
Legend: ✅ done & verified locally · 🧪 done, automated tests pending · 🚧 in progress · ⏳ not started · ⏭ deferred (Later)
Rule (AGENTS.md): checkboxes in the OpenSpec `tasks.md` files are only ticked once code is merged **and CI is green**;
this file tracks progress on the working branch (`feat/walking-skeleton-m1`).

## Phase 01 — foundation
| Task | Status | Notes |
|---|---|---|
| 0.1 Monorepo layout, uv, npm | ✅ | `apps/api` (uv, Python 3.13), `apps/web`, `deploy/`, `packages/diagram-design-system` |
| 0.2 compose.yaml + healthchecks + Makefile | ✅ | `archtwin-*` core, `archtwin-thirdparty-*` adopted services; ports chosen to coexist with Horizon |
| 0.3 init-env.sh (only OPENAI_API_KEY user-supplied, fake mode) | ✅ | `ARCHTWIN_LLM_MODE=fake|litellm` |
| 0.4 CI | ⏳ | |
| 0.5 structlog + redaction, /health/live, /health/ready | ✅ | OTel tracing ⏭ |
| 1.1 RequestContext, UUIDv7, RFC 9457, Idempotency-Key | ✅ | |
| 1.2 session-per-tx with `SET LOCAL app.*` | ✅ | `common/db.py::uow` |
| 1.3 outbox + relay (SKIP LOCKED, NOTIFY, backoff, dead-letter) + consumer receipts | ✅ | |
| 2.1 Keycloak realm, JWKS validation, 401 before DB | ✅ | demo users admin/alice/bob/vera/mallory |
| 2.2 Cerbos policies + policy tests | ✅ | 44 policy tests pass (`cerbos compile`) |
| 2.3 PlanResources → SQL via cerbos-sqlalchemy, unknown operator ⇒ deny | ✅ | |
| 2.4 envelope encryption + KeyProvider, redaction | ✅ | OpenBao adapter ⏭ |
| 3.1 org/project/env/membership tables, composite FKs, RLS | ✅ | `archtwin_app` role is NOBYPASSRLS |
| 3.2 project APIs (+ UI wizard) | 🚧 | API done; UI pending |
| 4.1 typed flag catalog generated from FLAG_CATALOG.md | ✅ | `scripts/gen-flag-catalog.py --check` |
| 4.2 OpenFeature provider, precedence, < 15 s propagation | ✅ | 5 s cache TTL |
| 4.3 security invariants immutable, attempts audited | ✅ | |
| 5.1–5.2 audit in same tx, hash chain, append-only, verify CLI | ✅ | `python -m archtwin.cli audit verify` |
| 7.1 LiteLLM aliases luna/terra/sol + fallback, Langfuse callback | ✅ | |
| 7.3 model picker API + server-side validation | ✅ | UI pending |

## Phase 02 — connectors
| Task | Status | Notes |
|---|---|---|
| 1.1 SDK protocol, manifest, registry | ✅ | git, docker, postgresql, http_openapi |
| 1.2 credentials sealed, test endpoint shows scopes/warnings | ✅ | |
| 1.3 egress guard | ✅ | private ranges denied unless allow-listed host |
| 1.4 Temporal scan workflow, flags re-checked at job start | ✅ | |
| 1.6 partial scans never tombstone | ✅ | builder uses latest complete scan + newer partial scans |
| 2.1–2.3 observations (append-only, versioned parsers), freshness, conflicts kept | ✅ | |
| 3.2–3.3 declared artifacts + tree-sitter detectors | ✅ | compose, Dockerfile, configs, OpenAPI, Backstage, CODEOWNERS, manifests, Python routes/imports, TS |
| 4.1 runtime discovery | ✅ | Docker Engine via read-only proxy (Kubernetes ⏭) |
| 5.1 PostgreSQL catalog (read-only tx), 5.3 sensitive columns | ✅ | |
| 7.1–7.2 uploads + passages | ✅ | Markdown/text native; PDF/DOCX via docling-serve profile |

## Phase 03 — architecture
| Task | Status | Notes |
|---|---|---|
| 1.1–1.5 graph, deterministic builder, identity merge/split, snapshots + diff, baselines (author ≠ approver) | ✅ | |
| 2.1 / 2.13 C4 views L1→L2→L3 + zoom navigation | 🚧 | API done; React Flow canvas pending |
| 2.5 Mermaid + Structurizr DSL export | ✅ | |
| 2.9–2.11 design-system tokens, ≤9 primary nodes, ≤2 focal, orthogonal router, 6-rule linter, SVG export | ✅ | 48/48 views of Horizon + ArchTwin lint clean |
| 3.1–3.2 MADR ADRs, immutable accepted versions | ✅ | |
| 4.1–4.3 documentation engine (evidence ids, protected manual sections, diff, Markdown export) | ✅ | |

## Phase 04 — drift
| Task | Status | Notes |
|---|---|---|
| 1.1–1.4 rule catalog, three-way coverage-aware evaluator, stable IDs, suppressions | ✅ | |
| 2.1 debounced graph build → drift evaluation | ✅ | `GraphBuildWorkflow` signal-with-start |
| 3.1 triage states, comments, reopen on recurrence | ✅ | |
| 4.1 in-app notifications + SSE | ✅ | |

## Phase 06 — intelligence
| Task | Status | Notes |
|---|---|---|
| grounded assistant with citation validation | ✅ | LiteLLM only; fake mode for CI |
| integration designer (2 options + Mermaid) | ✅ | |
| ADR drafting | ✅ | creates a proposed, AI-flagged ADR |

## Next
1. Web UI (React 19 + Vite + TanStack + React Flow + elkjs) — 🚧
2. Automated tests: unit (builder, drift truth table, flags, crypto, egress, audit, linter, exports), integration (RLS isolation), e2e journey
3. CI workflow
4. Full e2e run against Horizon, docs update

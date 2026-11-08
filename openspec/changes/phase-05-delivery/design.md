# Design: Plans, task execution and delivery alignment

## Context
Implements `specs/` of this change. ADR-0006 (read-only connectors, approved write-back) applies.

## Goals / Non-goals
- **Goals:** planning hierarchy, explicit work-item links, evidence chain, status semantics, report-only gates, controlled write-back.
- **Non-goals:** replacing Jira/Taiga/GitHub project management, AI-only fuzzy linking, LLM-based blocking.

## Status axes (kept separate)
| Axis | Source | Example values |
|---|---|---|
| Reported | issue tracker (per-connector status mapping) | To do, In progress, Done |
| Code | Git provider | PR open, merged (commit SHA) |
| Build | CI | build passed, image digest |
| Runtime | K8s/OTel observations | deployed (digest in workload), observed (edge seen) |
| Verified | ArchTwin rule | expected change present in runtime snapshot |

Computed stage = most advanced *evidenced* stage; gaps are listed explicitly.

## Decisions

| # | Decision | Adopted OSS | Notes |
|---|---|---|---|
| D1 | Links are created only by explicit user action or deterministic references (issue key in branch/PR title/commit message, e.g. `PROJ-123`) | — | AI may suggest; never auto-link |
| D2 | Status mapping tables per connector/project, versioned; unknown statuses kept raw and flagged | — | — |
| D3 | Build ↔ runtime correlation by **image digest** | — | Tags are mutable; digests are not |
| D4 | Conflict handling: both revisions kept; user resolves; no last-writer-wins | — | — |
| D5 | Write-back: flag + Cerbos `write_external` + preview diff + explicit Apply + idempotency key + audit | — | Implemented as a Temporal workflow with a human-approval signal |
| D6 | Gates output **SARIF** + JUnit; results signed with **cosign** (keyless where available) or in-toto attestations | SARIF, Sigstore cosign | GitHub/GitLab render SARIF natively; no custom CI UI |
| D7 | Blocking requires deterministic rule + fresh evidence + owner-approved enablement; unknown evidence follows an explicit fail-open/closed setting | — | LLM outputs never block |

## Risks / trade-offs
| Risk | Mitigation |
|---|---|
| Link coverage low because teams don't reference issue keys | CI template and PR template nudges; manual link UI; coverage metric |
| Tracker data quality varies | Raw status preserved; mapping review UI |
| Write-back mistakes | Preview + approval + idempotency; disabled by default |

## Rollback
Disable module/write-back/blocking flags. Remote writes already applied are listed in audit with links for manual revert.

## Open questions
- Which tracker first for pilots (Jira vs Taiga vs GitHub Issues)? Decide from M0 interviews; GitHub/GitLab issues ship first as they come free with phase 02.

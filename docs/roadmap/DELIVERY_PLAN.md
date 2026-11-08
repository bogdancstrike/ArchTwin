# Delivery roadmap — build the vertical value, not all 38 modules at once

All durations below are **planning ranges for one strong engineer assisted by AI**, not delivery commitments. Security and stabilization can increase effort substantially. Start with a 5–10 service project and a controlled Kubernetes/Swarm environment.

| Phase | Increment / target | Indicative effort | Exit demonstration |
|---|---|---|---|
| 01 | Secure foundation | 4–8 weeks | Project A/B isolation, Keycloak/Cerbos, flags, audit, basic model and UI |
| 02 | Connector-backed inventory | 6–12 weeks | GitHub/GitLab + K8s + PostgreSQL/Kafka inventory with evidence; Taiga/Jira basic read-only sync |
| 03 | Living diagrams/docs | 6–10 weeks | C4 diagrams generated from graph, manual edits preserved, ADR, docs/diff/export |
| 04 | Continuous drift | 4–8 weeks | Webhook→scan→normalized evidence→drift alert within measured SLO |
| 05 | Plans and implementation | 4–8 weeks | initiative → Jira/Taiga task → commit → deployment with evidence stages |
| 06 | AI and integration design | 6–10 weeks | authorized A/B analysis returns 2 options, diagrams, trade-offs and ADR draft via LiteLLM/Langfuse |
| 07 | Enterprise maturation | 8–16+ weeks | HA/restore, plugin SDK, portfolio metrics, security and scale testing |

**Caution:** These phases overlap in practice, and the full project can require sustained multi-year work. Do not use this table to imply a date for production readiness.

## Release milestones with economic validation
### M0 — Design partner discovery
- Interview 8–12 architects across different organizations, each with current tooling and painful architecture drift examples.
- Collect 10 known architecture changes (correct ground truth), 10 ADRs, 10 issue-to-deployment examples, permission model, and sample contracts.
- Identify whether buyers want *living diagrams*, *drift alerts*, *planning traceability*, or *cross-platform AI integration* most urgently.

### M1 — Compelling local proof of value (subset of phases 01–03)
- Create project, connect GitHub/GitLab and one K8s or Swarm environment, discover 5–10 services and database/topic edges.
- Render C4 container diagram + evidence inspector, compare two commits, export Markdown/Structurizr.
- Prove a stable system model for one pilot before building AI.

### M2 — Repeatable drift value (phases 04–05)
- Baseline a project, merge a route/topic change, see drift with source evidence, add ticket link, verify deployment.
- Test slow/unreachable source and deliberately show `UNKNOWN` instead of false deletion.
- Measure alert quality, end-to-end latency, and setup time.

### M3 — Architect intelligence (phase 06)
- Two projects with independent Keycloak/Cerbos scopes and explicit federation.
- Ask how to integrate A and B; generate REST vs event alternatives, risk/decision matrix, C4/sequence, ADR and work drafts.
- Validate zero cross-project leakage and no remote writes without approval.

### M4 — Enterprise beta (phase 07)
- Multiple orgs and 20+ projects, HA/backup/restore, multi-provider inventory, policy packs, pentest, connector SDK and SLO dashboards.

## Scope management
- Scope first release to GitHub, GitLab, Kubernetes, PostgreSQL, Kafka, Docling, manual architecture entry; Taiga/Jira basic read-only issue sync may enter once the core graph works.
- Delay Git write-back, automatic code changes, contract transformations, broad semantic retrieval and deep AI refactoring until measured demand.
- Never promise universal architecture inference from source code. Recognize uncertainty from dynamic calls, reflection, generated clients and runtime gaps.

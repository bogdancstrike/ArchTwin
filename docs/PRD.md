# Product Requirements Document — ArchTwin

## Problem statement
Architecture governance fails when system diagrams, ADRs, issue trackers, code and runtime state evolve separately. An architect must manually integrate conflicting signals and often learns of change after production drift occurs. Existing catalogs, diagramming tools and developer portals individually solve useful parts of this workflow, but not the full evidence-backed planning→implementation→observation loop.

## North-star outcome
**Time to trustworthy architectural understanding**: from selecting a project or asking an architecture question to receiving a current, permission-scoped, source-backed answer with clearly labeled uncertainty.

## Core personas
| Role | Most valuable workflow | Allowed actions |
|---|---|---|
| Enterprise architect | Portfolio landscapes, cross-platform integration, target standards, systemic risk | Scoped portfolio + approved federation |
| Solution architect | Project design, C4 views, interface contracts, ADR approval | Draft/approve architecture within scoped projects |
| Principal/staff engineer | Compare code/runtime/target, change impact, rollout checks | Read evidence, propose changes, review drift |
| Tech lead | Connect Jira/Taiga plan to commits and deployments | Link tasks, inspect status, suggest corrections |
| Platform/SRE | Monitor live infrastructure drift, incident dependencies | Read runtime, acknowledge findings, manage monitors |
| Engineering manager | Milestone and evidence-based status, risks | Aggregate assigned project metrics; no implicit raw-data access |
| Security architect | Trust boundaries, authorization policy, audit and review | Scoped audit and policy decisions |
| External reviewer | Time-bound review of selected diagrams/ADRs | Read only explicitly shared artifacts |

## Project concept — first-class isolation unit
- **Organization** owns shared policies, users, connector types, portfolio rules and retention defaults.
- **Project** has independently scoped identity, ownership, goal, external platform identifier, environments, access policies, documents, architecture elements, baselines, connectors, tasks and AI budget.
- **Environment** is a separate desired/observed state namespace (dev/test/staging/prod/custom).
- **Platform** is an architectural system represented *within* a project, with internal containers, components, interfaces and runtime deployment mappings.
- A project MAY contain multiple platforms, and one platform MAY be visible as a shared reference across projects only with explicit scope grants and a stable cross-reference.
- **Portfolio** is an organization-level **view**, not a hidden data-sharing backdoor.

## Eleven architect workflows
1. Create a project, name scope, owners and boundaries; register two environments and repository connectors.
2. Sync GitHub/GitLab, discover Spring Boot/FastAPI APIs, Kafka topics, PostgreSQL dependencies, Kubernetes/Swarm workloads.
3. Build/refine a C4 system context and container map; edit relationships and trust boundaries; save a reviewed baseline.
4. Import existing architecture docs with Docling; link statements to graph evidence; generate living documentation.
5. Design an initiative: draft solution architecture, compare options, publish ADR, bind milestones and Jira/Taiga issues.
6. Review planned vs implemented-in-code vs deployed vs verified; never conflate Done with deployed.
7. Receive drift alerts promptly after a merged commit or cluster change; triage with evidence and suppress noisy differences temporarily.
8. Compare architecture between dates/releases/environments; show timeline of important changes.
9. Ask "How can I connect platforms A and B?" across authorized projects. Generate REST vs Kafka vs CDC alternatives with interface diagrams, auth/trust trade-offs, failure modes and ADR draft.
10. Run a what-if scenario: loss of broker/topic/service, breaking contract, database region outage; see structural impact and uncertainty.
11. Export a complete review package: current graphs, diagrams, ADRs, tasks, plan status, drift, artifacts and verifiable source manifest.

## Functional scope
The 38 capabilities are specified as sequential OpenSpec changes in `openspec/changes` and grouped into 7 release increments. **Core security** is mandatory across every increment. Extended connector providers, write-back, semantic search, automatic notifications and generated docs are independently feature-flagged.

## Product differentiation
- Evidence types: declared intent, static code signal, operational observation, manual assertion, task status, LLM inference. Never merge without preserving origin.
- Architecture as a continuously versioned **product state**, not a screenshot.
- **Architect-first** C4 views with diagram editing and source-driven regeneration.
- Complete decision-to-deployment traceability and project-specific flags.
- Questions across platforms are answered with **design options**, not fabricated certainty.
- Trusted security model for cross-project use; strong accountability over automation.

## Explicit non-goals (MVP)
- Replacing Jira, Taiga, GitHub, GitLab, Keycloak, ArgoCD, Datadog, Backstage or Structurizr.
- Arbitrary AI agent execution with infrastructure write access.
- Building a general RAG assistant disconnected from architecture evidence.
- Perfect static call-graph extraction for all languages/frameworks.
- Automatically inferring business semantics from incomplete telemetry as ground truth.
- Fully automatic architecture remediation or topology changes.
- On-prem model serving in v1; **the abstraction is prepared but OpenAI is the enabled provider**.

## Success measures (pilot targets, NOT existing performance)
- First useful, provenance-backed container diagram ≤30 minutes from a small 3–10 service repo+K8s setup.
- 95% of high-confidence changes in piloted Git/K8s assets represented within 5 minutes of event receipt under normal operating conditions; expose p50/p95 and alert on breach.
- <5% false-positive rate for a selected benchmark drift taxonomy after rule tuning, measured against labeled incidents.
- ≥90% of architecture answers in a curated benchmark cite correct authorized sources and correctly label unsupported claims.
- ≥80% of active pilot architecture initiatives have traceability from ADR to work item and code or deployment evidence.
- Every cross-project access and model call is authorized, metered and attributable.

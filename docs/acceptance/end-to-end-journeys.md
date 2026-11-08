# End-to-end acceptance journeys

Each scenario includes a happy path, isolation case and failure path. Every delivery increment must demonstrate the relevant journey with stored test evidence.

## E2E-01 — Project and scope isolation
**Given** Org A has `Orion`, `Nova`, Org B has `Borealis`, and an architect can access only `Orion`; **when** the architect opens project search, graph navigation, exports, AI assistant and cached diagrams; **then** only `Orion` data can appear, with no leakage in entity counts, autocomplete, traces or links. Permission revocation invalidates saved results.

## E2E-02 — Inventory from code and runtime
**Given** Orion runs three Spring Boot services, one FastAPI service, PostgreSQL, Kafka and Kubernetes; **when** Git + cluster + data connectors scan; **then** the canonical graph contains discovered services, routes/topics/schema/deployment edges and source evidence. Discovered fields distinguish static vs observed vs inferred.

## E2E-03 — Living diagram edit
**Given** a generated C4 container diagram and manually positioned nodes; **when** a new service is discovered and diagram is regenerated; **then** confirmed nodes stay pinned, new nodes show with evidence, and the architect can accept/discard without overwriting layout history.

## E2E-04 — Three-way drift (critical)
**Given** desired baseline shows A publishes Kafka topic `orders.v1`, code stops publishing, runtime source is healthy and confirms no producer; **when** merged commit/webhook and reconciliation complete; **then** drift is classified with desired/static/runtime proof, assigned owner, rule version, and tracked latency. A stale runtime connector instead yields `UNKNOWN` and no false deletion alert.

## E2E-05 — Jira / Taiga plan state
**Given** milestone `M2` links Jira issue J-101 and Taiga task T-32; **when** issue statuses become Done but no deployment is observed; **then** external status reads Done, implementation stage is `implemented-in-code` or `unverified`, and architects can inspect missing deployment evidence. With Taiga connector flag OFF, no task synchronization occurs.

## E2E-06 — Cross-platform integration design
**Given** architects have explicit access and federation grant for projects Orion and Nova; **when** they ask "How can I connect A and B?"; **then** the assistant produces two+ viable patterns with diagrams, security/trust boundaries, latency/consistency, failure handling, APIs/events, source citations and missing requirements. The answer is a draft, and no external action runs without approval.

## E2E-07 — Cross-project denial (security critical)
**Given** architect may view Orion but not Nova; **when** an issue description or repo README asks the AI to include Nova secrets; **then** the policy prevents retrieval, returns a useful scoped refusal and records an audit event. Langfuse contains metadata but no secret contents.

## E2E-08 — Connector outage and recovery
**Given** GitLab is unreachable for 6 hours; **when** drift engine runs; **then** last known observations remain queryable, source is stale/degraded and no missing/deleted element is asserted. Reconciliation resumes from cursor after recovery and idempotently converges.

## E2E-09 — AI provider failure
**Given** LiteLLM cannot reach OpenAI; **when** user requests AI integration design; **then** job fails with actionable status and no partial architecture applied. Non-AI inventory, diagrams and drift continue to function. Langfuse failure cannot bypass security.

## E2E-10 — Security, approval and write-back
**Given** task creation is enabled for GitLab but user is viewer; **when** AI drafts tasks and user tries to apply; **then** Cerbos denies. An authorized architect with approval may preview and confirm; remote API gets an idempotency key and status is audited.

## E2E-11 — Historical reproducibility
**Given** architecture snapshots S1 and S2; **when** user reopens report generated at S1; **then** cited evidence and historical graph remain consistent, while current status and stale/revoked access are clearly indicated.

## E2E-12 — Cloud/on-prem extension
**Given** OpenAI-based AI profile in initial release; **when** an administrator later registers approved vLLM behind LiteLLM; **then** model profile routing changes without altering core app service code, after security/eval gates pass. This is a **future acceptance scenario**, not MVP delivery.

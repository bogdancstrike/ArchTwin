# Integrating platforms A and B — reference problem solving

## Example scenario
Project **Orion** (Spring Boot, PostgreSQL, Kafka, Keycloak) needs to exchange customer status with Project **Nova** (FastAPI, PostgreSQL, an external public API). The architect asks:
**"How can I connect Orion and Nova with secure near-real-time updates and no shared database?"**

### Retrieval workflow
1. Authenticate with Keycloak; project A+B authorization + federation grants verified using Cerbos before **any** graph node enters context.
2. Discover each system's APIs, event topics, schemas, trust boundaries, data ownership, runtime network reachability, latency requirements, and existing ADRs.
3. Mark missing requirements (e.g., acceptable latency, idempotency semantics, network peering) as unresolved questions.
4. Construct a **minimum-necessary source-backed context** and call `architecture-design` model profile via LiteLLM; Langfuse captures sanitized cost/latency trace.
5. Validate model citations against selected evidence IDs; reject ungrounded platform claims; generate alternatives and trade-off matrix.
6. Render proposed deployment/sequence diagrams and versioned ADR draft; only a human can approve and link tasks.

### Option comparison to present
| Option | Consistency and latency | Risks / requirements |
|---|---|---|
| Authenticated REST API | Request/reply, synchronous dependency | token audience, rate limiting, timeouts, retries, circuit breaker, network ACLs |
| Kafka event contract | Async propagation, eventual consistency | schema registry, ownership, retries, DLQ, idempotent consumers, outbox, ordering |
| Batch export/import | High delay, least runtime coupling | scheduling, checksums, encrypted transfer, replay and reconciliation |
| CDC from owning DB | Low application-change cost but tighter coupling to storage schema | data ownership, schema evolution, privacy review, permission boundary |

### Output contract
- **Decision context**: question, assumptions, evidence snapshot, missing facts.
- **At least two options** with diagram, interface definition, security assumptions, NFRs, effort and operations burden.
- **Recommendation with reasons** tied to explicit requirements; not falsely certain.
- **Threat model delta**: trust boundaries, credential lifecycle, leakage points, failure-mode analysis.
- **Artifacts**: C4 context/container view, two sequence diagrams, ADR proposal, API/AsyncAPI sketch, checklist and optional task drafts.
- **Approval**: architect reviews; no remote Jira/Taiga write or infrastructure change without explicit approval, policy and feature flag.

### Failure scenarios the assistant must address
- What happens when B is unreachable for 24 hours?
- How are duplicates and out-of-order updates handled?
- Which service owns and validates status fields?
- How do services verify Keycloak issuer/audience and distinguish user vs service principals?
- Can revocation propagate to caches and retained event payloads?
- What happens when contract v2 and consumer v1 coexist?
- What is observable at end-to-end trace and business event level?
- Are data classifications and federation grants compatible?

### Evaluation criteria
Reject or mark incomplete proposals that omit identity propagation, ownership, idempotency, data classification, outage handling, measurable latency and source evidence. AI-generated diagrams MUST remain drafts.

# Testing strategy by layer

## Unit
- Canonical entity identity reconciliation, graph diff, temporal validity, rule severity, source confidence, stale/unknown semantics, flag precedence, cost budgets, issue status mapping, citation validation.

## Integration (real backing dependencies)
- PostgreSQL transactions/outbox, row security and tenancy, Cerbos PDP test policies, Keycloak OIDC/JWKS rotation, LiteLLM proxy and Langfuse tracing metadata, Docling document parsing with quarantine, Redis cache revocation, Temporal workflow retries.
- Use provider sandbox/mock servers for GitHub/GitLab/Jira/Taiga, webhook signatures, paging, rate limit and cursors.

## Contract
- OpenAPI clients, connector SDK schemas, Kafka/Temporal event formats, API versioning, diagram JSON and Structurizr/Mermaid export stability.

## E2E
- Playwright tests for architect project home, C4 diagram, drift triage, task linkage, assistant A/B integration, permissions and export.

## Security
- Matrix-driven resource authorization and BOLA; cross-org/project oracle attacks; RLS with pooled connections; policy adapter AST unknown fields; prompt injection and source poisoning; SSRF redirect/rebinding; malware; signed webhooks; secrets in Langfuse/metrics; remote write approval bypass.

## Resilience
- Worker restart exactly between DB commit and event ACK; duplicate webhook; clock skew; pagination cursor expiry; provider outage; stale connector; outbox backlog; PDP unavailable; DB failover; Langfuse outage; LiteLLM rate limit; malformed AI JSON; K8s UID recreation; issue conflict.

## AI
- Curated 20 integration cases, 40 grounding questions, 50 injection cases; blind human architect rubric with evidence IDs and exact unsupported-claim checks. Re-evaluate after any model/profile/prompt change.

## Performance and UX
- Benchmark S/M/L workloads from `NFR_SLOS.md`, CI regression gate for graph queries, diagram editor node virtualization, WCAG keyboard paths and contrast, minimal responsive layout.

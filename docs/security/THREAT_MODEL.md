# Security architecture and threat model (mandatory from day one)

## Protected assets
Architecture diagrams, deployment topology, network boundaries, source code metadata, connector tokens, uploaded internal documents, issue tracker data, system identifiers, personal data, AI prompts and traces, exported reports, audit logs, model routing configuration.

## Trust boundaries
1. Internet/browser ↔ reverse proxy ↔ FastAPI; Keycloak JWT validated server-side for every request.
2. App ↔ Cerbos; policy decisions are not cached beyond their validity or permissions revision; fail closed if unavailable.
3. API ↔ worker queue; signed scoped job context, service auth and re-authorization when executed.
4. Worker ↔ external connectors; untrusted source data, strict egress allowlists, no unrestricted RFC1918 probing.
5. Worker/API ↔ LiteLLM; only LiteLLM holds external OpenAI API key; scoped service keys and per-org budgets.
6. LiteLLM ↔ OpenAI; sensitive data minimization, explicit org model policy, region and retention review.
7. App ↔ Langfuse; redact prompt payloads and document content by default; project-level content collection only by explicit opt-in.
8. PostgreSQL ↔ search/projection stores; query-time authorization and ACL re-check, including cached answer retrieval.
9. Project A ↔ Project B; explicit federation grant and entitlement for both scopes, no implicit shared-cache access.

## STRIDE-like controls
| Threat | Controls | Test |
|---|---|---|
| Cross-tenant IDOR | Cerbos authz, transaction-scoped tenant context, scoped FK, RLS defense | Enumerate random A/B project IDs with user A |
| Privilege escalation via AI | LLM never decides authority; tools execute under user principal; deny-default | Prompt injection asks to read hidden project |
| Cross-project retrieval leak | scope before retrieval, ACL revision in cache keys, per-citation revalidation | Embed cross-tenant matching text; no response/count leak |
| Connector token theft | secret envelope encryption, KMS/Vault provider, short-lived tokens, no browser/API returns | Search API/logs/traces for planted canary secret |
| Webhook spoofing | HMAC/signatures, replay window, provider IDs, exact path mapping | Invalid signature and replayed events rejected |
| SSRF through connectors/files | DNS rebind defense, IP allow/deny, redirects revalidation, egress proxy | Attempt to fetch IMDS/loopback/RFC1918 targets |
| Malicious document | MIME/content validation, AV scan, sandbox Docling, decompression limits | Zip bomb / malformed PDF cannot exhaust worker |
| XSS and diagram injection | CSP, sanitized Markdown/HTML, no untrusted Mermaid HTML labels | HTML/script in issue title not executed |
| Supply chain compromise | SBOM, signature verification, dependency pinning, CI scanning, plugin sandbox | Unapproved connector plugin fails activation |
| Audit tampering | append-only log, sequential digest/manifest, restricted deletion | Alter export then verify fails |
| Excessive AI data disclosure | minimization/redaction, project AI allowlist and consent, no sensitive data in default traces | Secret detector test of model input and Langfuse metadata |
| Runaway costs/queues | quotas, max concurrency, circuit breaker, timeouts, kill switches | Multi-tenant overload fairness tests |
| DoS through graph traversal | depth/node caps, query timeout, rate limits and pagination | 100k-edge test bounded memory/time |
| Dangerous remote writes | connector write-back OFF; typed commands, approval, idempotency, dry-run | AI instruction cannot create issues without user approval |
| Supply-chain poisoned source text | retrieved text untrusted, prompt boundaries, strict tool policies | Malicious README instructs policy bypass and fails |

## Identity and permissions
- Keycloak groups/claims are authenticated but not sufficient for all project roles; keep authoritative memberships and grants in PostgreSQL and policy inputs versioned.
- Roles: `org_owner`, `org_admin`, `security_admin`, `project_owner`, `architect`, `tech_lead`, `contributor`, `reviewer`, `viewer`, `integration_bot`, `break_glass` (time-bounded). Separation of duties for accepted ADRs, baseline publication and connector write-back.
- Resource attributes: `org_id`, `project_id`, `environment`, `classification`, `owner`, `sensitivity`, `state`, `shared_with`, `data_residency`, `effective_at`.
- Actions: `view`, `query`, `edit`, `approve`, `publish`, `connect`, `share`, `export`, `run_scan`, `ack_drift`, `write_external`, `manage_flags`, `read_audit`.
- Cerbos `PlanResources` can produce filters for searchable resources; translate its AST using a tested adapter and **deny** unknown operators. Explicit `CheckResources` for individual sensitive entities and mutations. Never pass raw Cerbos AST to client.
- Background jobs capture principal, organization, project, environment and permission snapshot revision, then **re-evaluate current entitlements** before writes and sensitive reads.

## Security workflows
- Connector setup: request least-privileged provider scopes → create secret ref → test through egress guard → show effective data visibility → approve → start initial sync.
- AI query: authorize scopes → build minimal evidence → classify/redact → enforce budget/provider policy → LiteLLM → validate citations and filter output → authorized storage → audit.
- Cross-project federation: both project owners (or delegated policy) approve exact data classes and expiry → evaluate at each query → revocation invalidates caches and saved answers.
- Incident: revoke connector token, disable type/project flag, stop active jobs, invalidate sessions or scoped keys and export audit with integrity digest.

## Required security test suites
- OIDC issuer/audience/JWKS rotation, replay and expired token tests.
- Per-resource Cerbos decisions and PlanResources SQL-filter adapter fuzz/property tests.
- BOLA/IDOR, multi-tenant graph edges, project-scoped FTS/vector/graph retrieval, cache invalidation, stale ACL handling.
- Malicious HTML/PDF/README/webhook, SSRF including redirects and DNS rebinding, archive bombs, connector sandbox failures.
- Broken signatures, prompt injection through every ingestion source, remote write authorization bypass.
- Restore consistency, secret revocation, key rotation, encrypted export and tenant deletion.

## Operational defaults
Fail closed on authorization; allow only approved OpenAI gateway model aliases; redact AI prompt content in tracing; scanners read-only; all write-back flags disabled; verify webhook signatures; use TLS/mTLS internally where appropriate; never store plaintext API keys in repo or logs. Record policy versions and explicit break-glass events.

# Reference multi-project portfolio — synthetic demonstration data

## Organization: Acme Engineering (synthetic)
### Project Orion — Order Platform
- Scope: order acceptance, fulfillment lifecycle, transactional state; prod and staging.
- Owners: platform team. Repositories: `acme/orders-api`, `acme/orders-worker`.
- Runtime: K8s deployments `orders-api` and `orders-worker`.
- Data: PostgreSQL `orders`, Kafka `orders.created.v1`.
- Desired architecture: API publishes order-created, worker consumes asynchronously, no direct cross-project DB access.
- Current code: Spring Boot publishes Kafka events; Java Spring Security validates Keycloak tokens.
- Work: Jira project ORI, issue ORI-102 "Expose status events".

### Project Nova — Customer Portal
- Scope: customer-facing portal, user status queries and notifications; prod.
- Repositories: `acme/customer-ui` React/Vite, `acme/customer-api` FastAPI.
- Runtime: Docker Swarm stack; Postgres for customer metadata.
- Work: Taiga project NOVA, user story 231 "Show order status".
- Desired integration: no cross-database table access; explicit data owner and security boundary.

## Federation
- Authorized design workspace may compare Orion + Nova contract metadata only (not customer records or secrets).
- Grant must be accepted by both owners, time-bound and classification-scoped.

## Cross-project question
"How can Orion and Nova connect so a user sees order-status changes within 30 seconds? Prefer loose coupling, no shared database, Keycloak SSO and robust retries."

### Expected options
1. Kafka event producer → sanitized event contract → Nova consumer projection (eventual consistency, idempotent consumer, DLQ, replay).
2. Secure REST BFF/API → OAuth2 client credentials/token exchange as authorized → client polling or webhooks (synchronous dependency).
3. Batch file integration explicitly deemed unlikely to meet 30-second requirement unless special assumptions hold.

### Drift fixture
- Baseline `orders.created.v1`, code changes to `orders.created.v2` and runtime consumer still on v1.
- Detection should record schema-contract drift and missing upgrade task, with evidence: Git commit, registry schema version, deployment observation, linked Jira issue.
- If registry connector unavailable, report `UNKNOWN`, not compatibility failure asserted as observed fact.

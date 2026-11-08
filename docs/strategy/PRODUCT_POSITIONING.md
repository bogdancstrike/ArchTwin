# Product assessment and positioning — explicit hypotheses

## Why this could matter
Software architectures are hard to keep consistent across diagrams, decisions, tasks, code and deployments. A continuously evidence-backed architecture history can reduce onboarding time, missing dependencies, review effort and risky changes. Your strongest wedge is **verified architecture drift coupled with the work needed to address it**, not generic "AI-generated architecture diagrams".

## Competitive environment (November 2026)
- **IcePanel**: collaborative C4 model/diagrams, future-state modeling and automation/sync with production. It is a serious direct competitor; cannot position ArchTwin as the first "living model" or first "AI diagrams from code". https://icepanel.io/
- **Structurizr**: strong C4 model-as-code with DSL and export ecosystem; use as an interoperability target. https://docs.structurizr.com/
- **Backstage**: extensible software catalog, TechDocs, Kubernetes, search and many plugins; partnering/interoperability preferable to replacing developer portal. https://backstage.io/docs/
- **Port**: software catalog/governed workflows and AI-triggerable actions; much of generic "portal plus agent" is already competitive. https://docs.port.io/workflows/overview/

## Differentiation to prove, not assert
1. Three-way declared / code / runtime evidence with strict UNKNOWN/stale semantics.
2. Architecture baseline approval, timeline/diffs and architecture conformance tied to tasks, commits, deployments.
3. Independent project scopes and secure explicit cross-project integration planning with source-backed tradeoffs.
4. On-prem/self-hosted deployment and policy-grade Keycloak/Cerbos identity/authorization.
5. OpenSpec-compatible, repeatable architecture decisions and verified implementation evidence.

## Strongest initial customer profile
- Companies with 20–300 engineers, 10–100 services, GitHub/GitLab + Kubernetes + Jira/Taiga, constrained architecture documentation and visible incidents from drift.
- Platform engineering, enterprise architecture and architecture review functions where runtime truth and approval process matter.
- Regulated/private environments needing on-prem deployment and explainable evidence, **not** organizations with a 2-service monolith and one diagram.

## Adoption hypotheses — NOT measured forecasts
- Free/open-source traction depends heavily on 10-minute setup, reliable automatic discovery and polished visual output. Assume many developers will test but far fewer configure multiple source connections.
- Design-partner funnel hypothesis: of 10 genuinely qualified architecture teams engaged in discovery, target 6 to finish first import, 3 to create reviewed baseline, 2 to use drift twice a month, 1 to request paid self-hosted support. These are targets to test, not empirical conversion rates.
- Early pilots should measure time-to-first-trustworthy-diagram, weekly architect engagement, meaningful drift findings, false-positive rate, saved manual effort, and % issue-to-deployment traceable.
- Avoid public claims of adoption percentage until actual installs, activation and retention telemetry exist.

## Three commercially viable packaging approaches
1. **Open-source core + paid enterprise**: C4 model, read-only discovery, diagrams and basic drift open; enterprise SSO/ABAC packages, advanced federation, audit retention/SLO, supported connectors and HA as paid services. Beware weakening baseline security for open source.
2. **Self-hosted managed license**: security-first enterprise buyer, predictable model cost and compliance; larger sales/support effort.
3. **Productized consulting wedge**: architecture modernization engagements use ArchTwin to produce inventory and drift reports, generating early revenue and user feedback without immediate SaaS scale.

## Biggest risks
- Competitive incumbents already cover diagrams, automation and developer catalogs; no easy novelty advantage.
- High trust bar: false positives/noisy drift can destroy adoption faster than missing a few extra features.
- Connector coverage is never complete; unknowns and plugin ecosystem are permanent product work.
- High onboarding friction due to repo/cluster/Jira permissions, cross-org legal/security review and data residency.
- Large scope, complex UI and AI cost can create an impressive demo but poor daily retention.
- Static code analysis cannot infer every dynamic runtime dependency; accuracy claims must be carefully bounded.

## Decision rule
Proceed only if M1 demo gets qualified architects to use the generated model **after** the first day, and M2 finds real architecture mismatches worth acting on. If adoption is weak, narrow to drift + traceability before building 30 additional modules.

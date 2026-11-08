# Capabilities and dependencies

```mermaid
flowchart LR
    P1[01 Foundation security/projects/flags] --> P2[02 Connectors and evidence]
    P2 --> P3[03 Architecture graph, diagrams, ADRs]
    P3 --> P4[04 Drift monitoring]
    P3 --> P5[05 Planning and task traceability]
    P2 --> P5
    P3 --> P6[06 AI & integration design]
    P4 --> P6
    P5 --> P6
    P6 --> P7[07 Enterprise hardening]
```

## Deliberately early cross-cutting work
- Authorization/security, project scoping, feature flags, audit and observability begin in phase 1 and are mandatory for every phase.
- Identity and evidence provenance are architectural foundations, not add-ons.
- Connector SDK interface and stable source IDs should land before individual adapters.
- AI's model gateway can be configured early for later usage; phase 6 unlocks user-facing AI functions only when grounded graph evidence exists.
- Define source quality and drift truth table before enabling near-real-time notifications.

## Capability ownership
`organizations`, `project-boundaries`, `identity-policy`, `feature-flags`, `audit-provenance` are separate bounded modules; inventory and graph may share PostgreSQL but not mutable DTOs. Connectors cannot write accepted architecture directly. Drift can read desired, static and observed snapshots but cannot mutate them. Assistant may draft artifact proposals, never directly approve or deploy.

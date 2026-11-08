# ArchTwin documentation

> Specification package — no implementation is claimed yet. Targets are design proposals, not measured results.

## Start here
| Document | What it answers |
|---|---|
| [PRD](PRD.md) | Problem, personas, workflows, scope and non-goals |
| [Product positioning](strategy/PRODUCT_POSITIONING.md) | Competitors, wedge, adoption hypotheses, decision rule |
| [Solution architecture](architecture/SOLUTION_ARCHITECTURE.md) | Containers, architectural states, persistence, diagrams, failure behaviour |
| [Architecture decisions (ADRs)](architecture/adr/README.md) | Why the key choices were made |
| [Technologies](TECHNOLOGIES.md) | Which open-source components are adopted, and what was rejected |
| [Implementation plan](IMPLEMENTATION_PLAN.md) | Walking skeleton, spikes, milestones, risk register, rollback |

## Architecture
- [Data model and invariants](architecture/DATA_MODEL.md)
- [Integration scenarios](architecture/INTEGRATION_SCENARIOS.md)
- Diagrams: [`context.mmd`](architecture/context.mmd), [`drift-and-ai-sequences.mmd`](architecture/drift-and-ai-sequences.mmd), [`structurizr-example.dsl`](architecture/structurizr-example.dsl)

## Building blocks
- Connectors: [contract](connectors/CONNECTOR_CONTRACT.md) · [support matrix](connectors/CONNECTOR_MATRIX.md)
- Security: [threat model](security/THREAT_MODEL.md) · [authorization matrix](security/AUTHORIZATION_MATRIX.md) · [Cerbos example](security/cerbos/README.md)
- AI: [architecture](ai/AI_ARCHITECTURE.md) · [evaluation plan](ai/EVALUATION_PLAN.md) · [model profiles](ai/MODEL_PROFILES.yaml) · [LiteLLM example](ai/litellm-config.example.yaml)
- Feature flags: [semantics](feature-flags/README.md) · [catalog](feature-flags/FLAG_CATALOG.md)
- API: [design](api/API_DESIGN.md) · [OpenAPI sketch](api/openapi.yaml)
- UX: [information architecture](ux/INFORMATION_ARCHITECTURE.md)

## Delivery and quality
- [Delivery roadmap](roadmap/DELIVERY_PLAN.md) · [dependencies](roadmap/DEPENDENCIES.md)
- [End-to-end journeys](acceptance/end-to-end-journeys.md) · [NFRs and SLOs](acceptance/NFR_SLOS.md) · [test strategy](acceptance/TEST_STRATEGY.md)
- [Spec index](SPEC_INDEX.md) · [requirement traceability](acceptance/REQUIREMENT_TRACEABILITY.csv)
- Ops: [deployment blueprint](ops/DEPLOYMENT_BLUEPRINT.md) · [repo layout](ops/REPO_LAYOUT.md)
- [Example portfolio](examples/PORTFOLIO_SAMPLE.md) · [references](RESEARCH_AND_REFERENCES.md)

## OpenSpec workflow
```bash
npm install -g @fission-ai/openspec
openspec list                                   # 7 phase changes
openspec validate --all --strict --no-interactive
openspec show phase-01-foundation
# in a supported agent: /opsx:apply phase-01-foundation
# archive ONLY after the phase is genuinely shipped: /opsx:archive phase-01-foundation
```
`openspec/specs/` stays empty until a phase is implemented and archived.

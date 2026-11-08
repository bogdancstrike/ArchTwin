# Grounding references for the specification package (checked November 2026)
- OpenSpec setup, change/spec/design/tasks schema: https://openspec.dev/docs/setup and https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md
- OpenSpec CLI `validate`, `status`, `archive` and workflow: https://openspec.dev/docs/cli
- C4 model view definitions: https://c4model.com/diagrams
- Structurizr DSL documentation: https://docs.structurizr.com/dsl
- Cerbos PlanResources and Query Plan enforcement: https://docs.cerbos.dev/cerbos/0.54.0/recipes/filtering-resources.html
- LiteLLM provider-neutral gateway and callbacks: https://docs.litellm.ai/docs/ and https://docs.litellm.ai/docs/observability/callbacks
- Langfuse support for LiteLLM-compatible gateways and connection concerns: https://langfuse.com/docs/administration/llm-connection
- Horizon repository (`bogdancstrike/horizon`) `deploy/litellm/config.yaml`, `backend/horizon/config.py` (read from connected GitHub for model alias reference; no secrets copied).


## Adopted open-source projects (see `docs/TECHNOLOGIES.md`)
- Keycloak https://www.keycloak.org/documentation · Cerbos query-plan adapters https://github.com/cerbos/query-plan-adapters
- OpenFeature https://openfeature.dev/ · Temporal https://docs.temporal.io/ · LiteLLM https://docs.litellm.ai/ · Langfuse https://langfuse.com/docs
- Docling https://github.com/docling-project/docling · tree-sitter https://tree-sitter.github.io/ · Syft https://github.com/anchore/syft
- OpenTelemetry servicegraph connector https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/connector/servicegraphconnector
- OpenTelemetry Demo (reference fixture) https://opentelemetry.io/docs/demo/
- React Flow https://reactflow.dev/ · elkjs https://github.com/kieler/elkjs · Motion https://motion.dev/ · Structurizr CLI https://docs.structurizr.com/cli
- diagram-design (MIT) https://github.com/cathrynlavery/diagram-design
- MADR https://adr.github.io/madr/ · Apprise https://github.com/caronc/apprise · Sigstore cosign https://docs.sigstore.dev/ · SARIF https://sarifweb.azurewebsites.net/
- CloudNativePG https://cloudnative-pg.io/ · Valkey https://valkey.io/ · SeaweedFS https://github.com/seaweedfs/seaweedfs · OpenBao https://openbao.org/

All architecture/acceptance targets in this package are design proposals, not claims about products or achieved performance. Verify specific connector APIs, model availability, licensing and runtime compatibility at implementation time.

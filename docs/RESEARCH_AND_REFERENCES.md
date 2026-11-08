# Grounding references for the specification package (checked November 2026)
- OpenSpec setup, change/spec/design/tasks schema: https://openspec.dev/docs/setup and https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md
- OpenSpec CLI `validate`, `status`, `archive` and workflow: https://openspec.dev/docs/cli
- C4 model view definitions: https://c4model.com/diagrams
- Structurizr DSL documentation: https://docs.structurizr.com/dsl
- Cerbos PlanResources and Query Plan enforcement: https://docs.cerbos.dev/cerbos/0.54.0/recipes/filtering-resources.html
- LiteLLM provider-neutral gateway and callbacks: https://docs.litellm.ai/docs/ and https://docs.litellm.ai/docs/observability/callbacks
- Langfuse support for LiteLLM-compatible gateways and connection concerns: https://langfuse.com/docs/administration/llm-connection
- Horizon private repository `deploy/litellm/config.yaml`, `backend/horizon/config.py` (read from connected GitHub for model alias reference; no secrets copied).

All architecture/acceptance targets in this package are design proposals, not claims about products or achieved performance. Verify specific connector APIs, model availability, licensing and runtime compatibility at implementation time.

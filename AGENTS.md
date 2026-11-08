# Agent implementation instructions — ArchTwin
1. Read `README.md`, `docs/PRD.md`, `docs/architecture/SOLUTION_ARCHITECTURE.md`, `docs/security/THREAT_MODEL.md` and `openspec/config.yaml` before writing code.
2. Choose a single `openspec/changes/phase-*` increment and implement its tasks with tests. Never mark checklist items complete without evidence.
3. Treat architecture specifications as executable contracts. Each Scenario needs positive/negative test coverage (unit, integration or E2E).
4. Keep a modular monolith with bounded packages; do not add microservices until load/security measurements justify it.
5. Maintain identity propagation and Cerbos enforcement on **every** read and write; prevent cross-project data leaks in search, caches, LLM context, exports and event payloads.
6. Use Keycloak OIDC with validated tokens, no homegrown password system. Connector credentials remain server-side, encrypted, and inaccessible to the LLM.
7. All AI traffic goes through the LiteLLM proxy, with Langfuse telemetry. OpenAI is the only enabled provider at MVP; future on-prem model integration remains a configuration/adapter concern.
8. Structural drift is derived only from verified snapshots/rules. LLMs may explain and draft; never assert observed facts that evidence does not support.
9. Every major module/provider/AI operation has a typed feature flag checked server-side and again when a queued job starts.
10. Keep API schemas, migrations, ADRs, acceptance tests and operator documentation synchronized. No secrets in commits, tests, traces, exports or prompts.

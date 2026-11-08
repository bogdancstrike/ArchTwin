# Feature flag semantics and governance

**Every optional major module and connector needs two checks**: (1) UI visibility/control and API handler guard; (2) worker-side guard immediately before executing a queued action. Do not rely on frontend toggles for security. Core authn/authz/audit/secrets isolation are *invariants*, never disabled.

- Type-safe catalog: flag name, description, owner, introduced phase, constraints, default, rollout policy, dependencies, kill-switch behavior, test plan.
- Precedence: **global emergency-off** > regulatory/org prohibition > organization override > project+environment override > cohort/role > default. For immutable security invariants all evaluations return ON.
- Each flag evaluation includes principal, org, project, environment, rollout revision and timestamp. Denied results are no-op with audited reason.
- Evaluation caches use versioned revisions and 15s pilot propagation target; watchers recheck when started. Stale flag cache for high-risk actions = disabled.
- External write-back has separate `connectors.writeback.*` flags, explicit approval and idempotent command endpoint. Feature flag alone does not authorize a write.
- AI feature flags independently control assistant, ADR, diagram, integration, issue drafts and provider/payload permission.
- Critical drift monitoring can be paused by emergency-off without affecting browsing of last known architecture; pausing must be prominently shown as **monitoring disabled**.
- Every flag gets a test: OFF => no side effects, ON => authorized behavior, role denial, cached revision change, queued job after disable, rollback and audit.

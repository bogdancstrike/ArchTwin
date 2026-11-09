# Implementation tasks — phase-06-intelligence

Legend: **[MVP]** required for M3 · **[Later]** may slip. Check a task only with merged code and green tests.

## 0. Evaluation first
- [ ] 0.1 [MVP] Golden datasets in Langfuse: 40 grounding questions, 20 A/B integration cases, 50 injection cases over the fixture (`docs/ai/EVALUATION_PLAN.md`); thresholds agreed before feature work.
- [ ] 0.2 [MVP] Fake-LLM mode covers every pipeline path in CI; nightly real-model eval for each selectable model.

## 1. Architecture assistant — AT-ARCHITECTURE_ASSISTANT-001..004
- [x] 1.1 [MVP] Evidence-pack builder with deterministic tools, scope pre-filtering, manifest hash.
- [x] 1.2 [MVP] Structured responses + citation validator; unsupported-claim marking; UNKNOWN with last observation time.
- [x] 1.3 [MVP] Model picker (Luna default, Terra, Sol) wired to `/ai/models`; chosen model shown with each answer.
- [ ] 1.4 [MVP] Budgets, rate limits, cancellation, SSE streaming, Langfuse trace correlation.
- [ ] 1.5 [Later] Draft ADR / review / task suggestions as proposals with preview + Apply.

## 2. Federation — AT-CROSS_PROJECT_FEDERATION-001..003
- [ ] 2.1 [MVP] Bilateral grants (relation types, data classes, expiry) with approvals and audit.
- [ ] 2.2 [MVP] Per-query evaluation; revocation invalidates caches and saved answers (test).
- [ ] 2.3 [MVP] Integration-point discovery (APIs, topics, contracts, network zones) with unknowns.

## 3. Integration designer — AT-INTEGRATION_DESIGNER-001..003
- [x] 3.1 [MVP] Option generation schema and trade-off matrix; ≥2 options when viable, explanation otherwise.
- [ ] 3.2 [MVP] AI-drafted C4/sequence diagrams as view specs rendered by the diagram-design renderer; linter must pass.
- [ ] 3.3 [Later] ADR + task drafts with remote write only via phase-05 approval flow.

## 4. Impact analysis — AT-IMPACT_ANALYSIS-001..003
- [ ] 4.1 [MVP] Bounded blast-radius traversal with evidence and unknown edges; truncation notice.
- [ ] 4.2 [Later] Scenario branches (copy-on-write overlays) and comparison to baseline.
- [ ] 4.3 [MVP] Structural vs measured labelling; refusal to invent probabilities.

## 5. AI evaluations — AT-AI_EVALUATIONS-001..003
- [ ] 5.1 [MVP] Eval-gated model picker and `ai.*` flags; audited override.
- [ ] 5.2 [MVP] No fallback across data-residency policy; tool calls outside allowlist rejected.
- [ ] 5.3 [Later] vLLM/local profile documented and tested in a lab environment only.

## X. Phase exit gates
- [ ] X.1 A/B integration journey demo on two fixture projects with federation.
- [ ] X.2 Red-team: zero cross-project leaks, zero unapproved writes.
- [ ] X.3 Eval thresholds met per enabled model; cost per answer recorded.

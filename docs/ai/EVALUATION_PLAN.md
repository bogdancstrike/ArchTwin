# AI evaluation plan — compare prompts and models before rollout

## Golden datasets
- `A vs B integration`: 20 synthetic two-platform scenarios (REST vs async events, PII constraints, different IAM realms, disconnected networks, consistency assumptions).
- `Grounded project answer`: 40 graph/doc questions with allowed evidence references and expected uncertainty.
- `Diagram drafting`: 20 projects with hand-validated C4 structure; compare precision/recall of entities/edges and manual layout preservation.
- `ADR drafts`: 20 options with expected quality criteria (trade-offs, reliability, security, cost, reversibility).
- `Prompt injection`: 50 malicious source snippets embedded in Git docs, Jira tasks, PDFs and connector titles.
- `Cross-project isolation`: 50 queries spanning permitted/denied grants; **zero** leaks acceptable.

## Metrics and gates
- **Citation precision** ≥95% over golden sets; every cited evidence ID must exist in authorized pack.
- **Unauthorized data leakage** = 0 in red-team tests.
- **Unsupported assertion rate** <3% in high-confidence answer claims; uncertain labels are accepted when evidence missing.
- **Integration completeness** ≥90% coverage of ownership, auth, consistency, retries, idempotency, failure modes and observability checklist.
- Median/p95 token cost and wall-clock latency tracked per profile, connector corpus and environment.
- Human architect review of utility with blind comparison to baseline workflow before claiming productivity gains.

Run the full suite for every selectable model (`gpt-6-luna` default, `gpt-6-terra`, `gpt-6-sol`) — a model is shown in the picker only after it meets the thresholds — then the optional `gpt-5.6-luna` fallback and future on-prem models. **Do not assume equivalent quality or pricing.** Use Langfuse traces/evaluations and gateway usage metadata; pin dataset and model profile versions.

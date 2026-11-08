# Proposal: Plans, task execution and delivery alignment

## Why
Architects lose track between "we decided" and "it is running". Issue trackers say *Done*; that is not proof of deployment. This phase links initiatives and ADRs to work items, commits, builds and observed deployments, and keeps the external tracker's status as a separate axis from verified implementation. It also adds report-only architecture checks for CI.

Users affected: tech leads, architects, engineering managers.

## What Changes
- Add **Roadmaps, plans and architecture increments** (`architecture-planning`).
- Add **Taiga, Jira, GitLab and GitHub work tracking** (`issue-synchronization`).
- Add **Implementation evidence and delivery tracking** (`implementation-traceability`).
- Add **Architecture-aware release checks** (`release-gates`).

## Impact
- **Modules:** `planning`, `traceability`, `gates`.
- **Tables:** initiatives, milestones, changes, work_items (canonical view of external issues), work_item_links (explicit, user-confirmed), status_mappings (versioned per connector), evidence_chain (issue → PR/MR → commit → build → image digest → workload), gate_results.
- **APIs:** `/initiatives`, `/work-items/{id}:link`, `/requirements/{id}/trace`, `/gates/check` (CI), `/tasks/{id}:preview-remote-write`.
- **Adopted OSS:** provider SDKs from phase 02, SARIF output (rendered natively by GitHub/GitLab), Sigstore **cosign** / in-toto attestations for signed results, GitHub Actions / GitLab CI templates.
- **Flags:** `module.architecture-planning`, `module.issue-synchronization`, `module.implementation-traceability`, `module.release-gates`, `connectors.writeback.*`, `drift.blocking_ci`.

## Dependencies
Phases 02 (work connectors) and 03 (graph, ADRs); phase 04 for drift-based gates.

## Security risks
Unauthorized remote writes, AI-created links treated as facts, forged CI results.

## Rollout and rollback
Read-only sync first; links are explicit (user-confirmed). Gates start report-only (SARIF warnings). Write-back and blocking each need their own flag plus owner approval. Rollback = disable flags; no remote state is changed by this phase unless write-back was explicitly applied.

## Success
- A requirement shows its chain with stages and gaps: planned → in progress → implemented-in-code → built → deployed → observed → verified (or rolled back).
- "Done in Jira, not observed in prod" is shown as **unverified deployment**.
- CI receives a signed SARIF report; tampering is detected.

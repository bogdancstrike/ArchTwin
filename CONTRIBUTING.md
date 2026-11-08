# Contributing to ArchTwin

Thanks for your interest! ArchTwin is **spec-driven**: behaviour is agreed in [OpenSpec](https://openspec.dev) before code is written.

## Workflow
1. **Discuss** — open an issue describing the problem, affected users and evidence.
2. **Specify** — propose a change under `openspec/changes/<name>/` (`proposal.md`, `design.md`, `tasks.md`, `specs/**/spec.md`). Every requirement uses MUST/SHALL and has a positive and a negative scenario.
   ```bash
   npm install -g @fission-ai/openspec
   openspec validate --all --strict --no-interactive
   ```
3. **Decide** — significant technical choices get an ADR in `docs/architecture/adr/` (MADR format). Prefer adopted open source ([`docs/TECHNOLOGIES.md`](docs/TECHNOLOGIES.md)); custom infrastructure needs justification.
4. **Implement** — follow [`AGENTS.md`](AGENTS.md): tests for every scenario, security invariants never bypassed, feature flags for optional modules, expand/contract migrations.
5. **Review** — PRs link requirement IDs (e.g. `AT-DRIFT_ENGINE-003`) and tick only tasks backed by merged code and green CI.

## Commit style
[Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `spec:`, `chore:`, `test:`.

## Security
Never commit secrets, tokens or real customer architecture data. Report vulnerabilities privately to the maintainers rather than in public issues.

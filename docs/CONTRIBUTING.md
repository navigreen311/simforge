# Contributing to SimForge

SimForge is developed AI-assisted with Claude Code under the conventions in [`../CLAUDE.md`](../CLAUDE.md).

## Workflow

1. **Branch first:** all work happens on `ai-feature/<slug>` (kebab-case). Never commit features to `main`.
2. **Use the commands:** prefer `/impl-feature` for features, `/test-suite` for tests, `/code-review` before merge, `/api-test` for endpoints, `/deploy-prod` for deploy assets.
3. **The Recipe (every feature):** Plan (mini-PRD + arch) → Implement end-to-end → Tests (pass) → Verify (run + demo) → Docs (README + `docs/<feature>.md` + CHANGELOG) → Deliver (PR summary).
4. **Conventional Commits:** `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`, `ci:`. Every commit co-authored line per `CLAUDE.md` §4.
5. **Quality gates before "done":** lint + typecheck clean, tests written and passing, app boots. Close your own loop.

## Local setup

```bash
cp .env.example .env
./scripts/bootstrap.sh   # postgres + redis, install deps, migrate, seed
pnpm dev
```

## Tests

```bash
# backend
cd apps/api && pytest
# frontend
pnpm --filter web test
# whole monorepo
pnpm test
```

## PR checklist

- [ ] Branch is `ai-feature/<slug>`, rebased on latest `main`.
- [ ] Lint + typecheck clean (`pnpm lint && pnpm typecheck`, `ruff check && mypy`).
- [ ] Tests added/updated and passing.
- [ ] Docs updated (README / `docs/<feature>.md` / CHANGELOG).
- [ ] No secrets committed; no real PHI/PII.
- [ ] PR body: what, why, how to run, test results, risks, Fact-Check List for risky assumptions.
- [ ] Migrations include a rollback note and 2-reviewer sign-off (destructive → staging soak + Ivan sign-off).

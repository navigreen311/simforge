# /test-suite — Create or extend the automated test suite

Create or extend an automated test suite (unit, integration, e2e) and optionally wire it into CI.

## Arguments (`$ARGUMENTS`)
- `target`: path or module (e.g. `apps/api/src/services/evaluation`)
- `coverage_goal`: e.g. `80%` (SimForge core services target 80%, elsewhere 60%)
- `test_kinds`: any of `unit | integration | contract | e2e | load`
- `ci_provider`: `github-actions | none`
- `seed_data`: (optional) fixtures needed (mock VillageData fs, mock Forge adapters, seeded CCBs)

## Process
1. **Inventory** — list existing tests covering `target`; measure current coverage.
2. **Identify gaps** — enumerate untested branches, error paths, and edge cases (especially: sandbox isolation, gate auto-fail reasons, signature verification, fingerprint drift).
3. **Add tests** — write `test_kinds` against acceptance criteria. Backend `pytest` under `apps/api/tests/{unit,integration,contract,e2e}` mirroring `src/`. Frontend `vitest` + Playwright.
4. **Fixtures/teardown** — reusable fixtures: mock VillageData filesystem, mock Forge adapters, in-memory/test Postgres, `StubSigner`.
5. **Test scripts** — ensure `pnpm test`, `pytest`, and per-package scripts run the suite; report the exact commands.
6. **CI config** — if `ci_provider=github-actions`, update `.github/workflows/ci.yml` (lint, typecheck, unit, integration, contract).
7. **Run & summarize** — run everything; report pass/fail, coverage delta, and remaining gaps (never silently cap coverage — log what was skipped and why).

## Outputs
- New/updated tests, updated test scripts, CI config (if chosen), coverage report paths, a short summary of what is now covered vs. deliberately deferred.

## Example invocation
```
/test-suite target=apps/api/src/services/cert coverage_goal=80% \
  test_kinds="unit integration" ci_provider=github-actions \
  seed_data="StubSigner + seeded CertSnapshotPayload"
```

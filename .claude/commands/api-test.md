# /api-test — Generate API contract + integration tests

Generate API contract + integration tests from the FastAPI OpenAPI spec (or live endpoints).

## Arguments (`$ARGUMENTS`)
- `spec_path_or_url`: `http://localhost:8000/openapi.json` (default) or a path
- `auth_mode`: `clerk-jwt | dev-bypass | bearer-token`
- `env`: `local | staging`
- `test_style`: `pytest-httpx | schemathesis | playwright-request`
- `load_smoke`: `true | false` (optional light k6 smoke)

## Process
1. **Parse spec/endpoints** — enumerate routers/paths (see blueprint §C.3): agents, packs, scenarios, runs, certs, snapshots, gaps, dashboard, registry, lineage, constitution, attest.
2. **Generate success & error tests** — for each endpoint: happy path + validation errors (422) + authz failures (401/403 — every endpoint must enforce role) + not-found (404). For signing/verify endpoints, assert signature round-trips with `StubSigner`.
3. **Reusable client/helpers** — a typed test client with auth injection per `auth_mode`; shared fixtures for seeded agents/packs/runs.
4. **CLI for envs** — parametrize base URL + auth by `env`.
5. **Optional load smoke** — if `load_smoke=true`, a small k6 script hitting hot read paths (readiness-matrix, runs list).
6. **Run & summarize** — execute, report pass/fail + any contract mismatches (drift between OpenAPI and tests → fail).

## Outputs
- `apps/api/tests/api/` (or `tests/integration/api/`) with runnable suites.
- Example commands to run per env.
- Report paths + a short coverage-of-endpoints summary.

## Example invocation
```
/api-test spec_path_or_url=http://localhost:8000/openapi.json \
  auth_mode=dev-bypass env=local test_style=pytest-httpx load_smoke=false
```

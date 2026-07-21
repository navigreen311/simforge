# ADR-0030 — Deployable production seams

**Status:** Accepted (2026-07-21).

## Context
The platform's external integrations were built as **seams** — real code that ships in stub/local
mode and activates on config (auth, signing, Forges, LLM, Linear, integrated execution). What was
missing were the *deployment* artifacts to actually run them: a production image, a self-contained
stack, and a way to confirm at runtime which seams are live. Docker and a target cloud aren't
available in this environment, so the goal is **complete, validated, deployable artifacts** — not a
live cloud apply.

## Decision
- **Production API image** (`apps/api/Dockerfile`) — multi-stage (build wheels, slim runtime),
  **non-root** (`simforge` uid 10001), `HEALTHCHECK` on `/api/health/`, installs the validator
  package (a runtime dep) + the API, runs uvicorn.
- **Self-contained stack** (`infra/compose/docker-compose.full.yml`) — API + Postgres 17 + Redis +
  Prometheus + Grafana in one file. Grafana mounts the ADR-0029 provisioning + dashboards;
  Prometheus (`infra/compose/prometheus.yml`) scrapes the API `/metrics`; the API waits on healthy
  datastores.
- **Deploy-readiness endpoint** `GET /api/health/config` — reports the *mode* of every seam
  (`auth_mode`, `hsm_provider`, `forge_mode`, `llm_provider`, `integrated_execution_enabled`,
  `linear_enabled`, …) + an `all_stub` flag. **Never returns secrets** — modes only. This is how an
  operator confirms a prod deploy actually flipped the seams it intended.
- **Smoke test** (`scripts/smoke-test.sh`, extended) — liveness + readiness + seam-config + `/metrics`
  + a real endpoint. **Seam matrix** documented in `docs/deploy.md` (env var → stub→prod for each).

## Consequences
- The seams are now genuinely deployable: `docker compose -f infra/compose/docker-compose.full.yml
  up -d --build` brings the whole stack up; `/api/health/config` + the smoke test verify it; flipping
  a seam is one env var (per the matrix).
- What can/can't be verified here: the compose + Prometheus config parse and are complete, the
  Dockerfile is production-shaped, and the config/readiness/smoke checks run live against the API
  (all validated in CI + a live run). The actual `docker build` and cloud `terraform apply` need
  Docker / cloud credentials and happen at deploy time — the untested surface is the build/apply
  step, not the artifacts.
- `/api/health/config` guarantees a deploy can't *silently* run half-stubbed: `all_stub: true` in a
  "production" environment is an immediate red flag.

## Cross-references
Blueprint §J (deployment), §H.2 (metrics the stack scrapes), ADR-0016/0018/0022/0023/0024/0025/0029
(the seams this deploys), `docs/deploy.md` (seam matrix + compose recipe).

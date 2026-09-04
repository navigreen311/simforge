# Deployment (blueprint §J)

> Dev runs against native Postgres + Memurai (no Docker here) or `docker-compose`. Staging/prod
> assets below are **scaffolding** — review before applying.

## Environments
- **Dev:** `apps/api` (uvicorn :8000) + `apps/web` (`pnpm dev` :3000) against local Postgres/Redis. All external systems stubbed (ADR-0001).
- **Staging:** Fly.io apps `simforge-{web,api,workers}-staging`; deploys on merge to `main` (`.github/workflows/deploy-staging.yml`).
- **Prod:** AWS ECS Fargate (multi-AZ) + RDS Postgres (Multi-AZ + replica) + ElastiCache Redis + S3 (tiered) + CloudHSM + CloudFront. IaC in `infra/terraform/`.

## Observability
- `/metrics` (Prometheus) — `simforge_runs_total`, `simforge_readiness_gate_total`, `simforge_certs_issued_total`, `simforge_tokens_used_total`, `simforge_run_duration_seconds`, `simforge_pdp_decision_latency_seconds`, …
- Structured JSON logs (structlog) → Loki.
- **OTEL traces → Tempo** (ADR-0031). No-op unless activated: set `OTEL_EXPORTER_OTLP_ENDPOINT` (export) or `OTEL_TRACES_ENABLED=true` (build spans without exporting). FastAPI requests are auto-instrumented; `scenario.run` and `pdp.decide` add manual spans. The compose stack runs Tempo (OTLP/HTTP :4318) with a provisioned Grafana datasource; confirm with `tracing_enabled` in `GET /api/health/config`.
- Dashboards + alerts per blueprint §H.4/§H.5 (PagerDuty).

## CI/CD
- `ci.yml` — validator + api (hermetic SQLite) + web jobs on every PR/push.
- `pack-validator.yml` — validates `packs/` on change.
- `contract-tests.yml` — village_bridge + Forge-adapter contracts (v1.1).

**There is no deploy workflow.** `deploy-staging.yml` and `deploy-prod.yml` were deleted on
2026-09-04 (ADR-0045). Both were scaffolds whose only step was `echo`, and `deploy-staging`
had been passing green on every push to `main` for months, beside `ci ✓` and
indistinguishable from it, while deploying nothing. **SimForge has never been deployed
anywhere.** No workflow is an honest report of that; a green one is not, and a permanently
red one trains readers to ignore red. What they intended to do is written below instead,
where it is a plan rather than a job that passes.

## Prod deploy (how to)
```bash
# 1. Infra (once / on change)
cd infra/terraform && terraform init && terraform plan && terraform apply
# 2. Migrations (zero-downtime)
pnpm --filter @simforge/db migrate:deploy
# 3. Release: build+push images to ECR, blue/green deploy, gradual traffic shift 0→10→100%
#    Rollback = shift traffic back to the previous target group.
```

**None of the above has been run.** The terraform in `infra/terraform` has never been
applied, which means it has never been evaluated either — unapplied terraform is a
proposal. Step 3 has no automation behind it since ADR-0045; it is a description of the
pipeline somebody would write.

### The intent the deleted workflows carried

Kept because it is the only record of what was planned, and it is worth having when
somebody builds the real thing:

- **staging** (was: auto on push to `main`) — build and push images to ECR,
  `prisma migrate deploy`, deploy to Fly/ECS, run `scripts/smoke-test.sh`, then post-deploy
  contract verification.
- **prod** (was: `workflow_dispatch`, gated approval) — alembic/prisma migrate
  (zero-downtime), blue/green deploy, gradual traffic shift 0→10→100, post-deploy
  verification, rollback on failure.

Note that `scripts/smoke-test.sh` and the full compose stack below already exist, so a real
staging pipeline is closer than the absence of a workflow suggests.

## Seam configuration (ADR-0030)
Every external integration is a **seam** that ships in stub/local mode and activates on config. Flip
only what you intend to run for real, then confirm with `GET /api/health/config` (reports modes, no
secrets — `all_stub: false` once any seam is live).

| Seam | Env | Stub default → production |
|---|---|---|
| Auth | `AUTH_MODE` | `dev-bypass` → `clerk` (+ `CLERK_JWKS_URL`/`CLERK_ISSUER`) — ADR-0018 |
| Signing | `HSM_PROVIDER` | `stub` → `file` (`SIMFORGE_SIGNING_PRIVATE_KEY_PEM`) / `yubihsm` / `cloudhsm` — ADR-0018/0022 |
| Forges | `FORGE_MODE` + `FORGE_SANDBOX_URLS` | `local` → `http` (per-forge) — ADR-0016 |
| LLM | `LLM_PROVIDER` / `LLM_JUDGE_PROVIDER` | `stub` → `ollama` / `anthropic` / `auto` — ADR-0008/0023 |
| Gap tickets | `LINEAR_API_KEY` + `LINEAR_TEAM_ID` | no-op → real Linear issues — ADR-0029 |
| Integrated exec | `INTEGRATED_EXECUTION_ENABLED` | `false` (sandbox) → `true` (PDP-gated) — ADR-0025 |
| Revocation push | `REDIS_URL` | required for real-time PEP invalidation — ADR-0024 |
| Tracing | `OTEL_EXPORTER_OTLP_ENDPOINT` | off → OTLP/HTTP export to Tempo — ADR-0031 |

## Self-contained stack (compose)
The whole stack — API + Postgres + Redis + Prometheus + Grafana (dashboards pre-provisioned, ADR-0029) — runs from one file:
```bash
docker compose -f infra/compose/docker-compose.full.yml up -d --build
pnpm --filter @simforge/db migrate:deploy   # apply schema on first boot
./scripts/smoke-test.sh                      # liveness + readiness + seam-config + /metrics + forges
# Grafana → http://localhost:3001 (admin/admin) · Prometheus → :9090 · API → :8000
```
The API image (`apps/api/Dockerfile`) is a multi-stage, non-root, healthchecked build.

## Backups & DR
Daily RDS snapshots (30-day) + 7-day PITR + weekly cross-region copy. See `docs/RUNBOOKS/DR.md` (RPO 1h / RTO 4h).

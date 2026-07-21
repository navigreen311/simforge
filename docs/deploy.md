# Deployment (blueprint §J)

> Dev runs against native Postgres + Memurai (no Docker here) or `docker-compose`. Staging/prod
> assets below are **scaffolding** — review before applying.

## Environments
- **Dev:** `apps/api` (uvicorn :8000) + `apps/web` (`pnpm dev` :3000) against local Postgres/Redis. All external systems stubbed (ADR-0001).
- **Staging:** Fly.io apps `simforge-{web,api,workers}-staging`; deploys on merge to `main` (`.github/workflows/deploy-staging.yml`).
- **Prod:** AWS ECS Fargate (multi-AZ) + RDS Postgres (Multi-AZ + replica) + ElastiCache Redis + S3 (tiered) + CloudHSM + CloudFront. IaC in `infra/terraform/`.

## Observability
- `/metrics` (Prometheus) — `simforge_runs_total`, `simforge_readiness_gate_total`, `simforge_certs_issued_total`, `simforge_tokens_used_total`, `simforge_run_duration_seconds`, …
- Structured JSON logs (structlog) → Loki; OTEL traces → Tempo (wire `OTEL_EXPORTER_OTLP_ENDPOINT`).
- Dashboards + alerts per blueprint §H.4/§H.5 (PagerDuty).

## CI/CD
- `ci.yml` — validator + api (hermetic SQLite) + web jobs on every PR/push.
- `pack-validator.yml` — validates `packs/` on change.
- `contract-tests.yml` — village_bridge + Forge-adapter contracts (v1.1).
- `deploy-staging.yml` (auto on main) / `deploy-prod.yml` (manual, gated approval).

## Prod deploy (how to)
```bash
# 1. Infra (once / on change)
cd infra/terraform && terraform init && terraform plan && terraform apply
# 2. Migrations (zero-downtime)
pnpm --filter @simforge/db migrate:deploy
# 3. Release: build+push images to ECR, blue/green deploy, gradual traffic shift 0→10→100%
#    (via deploy-prod.yml, manual approval). Rollback = shift traffic back to the previous target group.
```

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

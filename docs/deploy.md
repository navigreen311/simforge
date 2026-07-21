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

## Backups & DR
Daily RDS snapshots (30-day) + 7-day PITR + weekly cross-region copy. See `docs/RUNBOOKS/DR.md` (RPO 1h / RTO 4h).

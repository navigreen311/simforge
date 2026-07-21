# /deploy-prod — Prepare production deployment assets & a repeatable pipeline

Prepare production deployment assets and a repeatable, idempotent pipeline. **This command prepares assets and pipelines — it never performs a live prod deploy without explicit Ivan approval** (Ivan-only, audited; see `CLAUDE.md` §15).

## Arguments (`$ARGUMENTS`)
- `platform`: `fly | aws-ecs` (blueprint: Fly.io for staging/small scale, AWS ECS Fargate for prod)
- `region`: e.g. `us-west-2` (+ replica `us-east-1`)
- `runtime`: `web | api | workers | all`
- `database`: `rds-postgres | fly-postgres | supabase`
- `secrets_source`: `aws-secrets-manager | fly-secrets`
- `zero_downtime`: `true | false` (blue/green + gradual traffic shift 0→10→100%)

## Process
1. **Architecture diagram** — target topology (ALB/Cloudflare → web + api → Postgres primary+replica → Redis → S3 → CloudHSM). Mermaid allowed.
2. **IaC / platform config** — Terraform under `infra/terraform/` (`rds.tf`, `redis.tf`, `s3.tf`, `ecs.tf`, `iam.tf`) or Fly `fly.toml`s. Never inline real secrets — reference `secrets_source`.
3. **Build/release scripts** — Docker builds, ECR/registry push, Alembic migration step (zero-downtime patterns), `prisma migrate deploy`.
4. **Rollout strategy** — blue/green for backend; gradual traffic shift; documented rollback.
5. **Observability** — confirm OTEL → Grafana, Sentry DSN, Prometheus `/metrics`, PagerDuty alerts wired.
6. **Staging deploy + smoke tests** — deploy to staging, run `scripts/smoke-test.sh`, post-deploy contract verification.

## Outputs
- Infra/workflow files (`infra/terraform/*`, `.github/workflows/deploy-*.yml`).
- `docs/deploy.md` (topology, env vars, rollout, rollback, DR pointers).
- A "how to deploy" command block (staging auto; prod gated on approval).
- A **Fact-Check List**: instance sizes, service quotas, region availability, monthly cost estimate.

## Example invocation
```
/deploy-prod platform=aws-ecs region=us-west-2 runtime=all \
  database=rds-postgres secrets_source=aws-secrets-manager zero_downtime=true
```

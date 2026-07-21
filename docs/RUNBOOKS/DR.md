# Disaster Recovery (blueprint §J.6)

**RPO:** 1 hour · **RTO:** 4 hours. SimForge is Tier-1: an outage blocks certification, which blocks Village autonomy expansion.

## Graceful degradation
During a SimForge outage, Village agents operate at their **last-known-certified autonomy level** (cached in PEPs). After 24h of outage, auto-downgrade all L5→L4, etc.

## Restore procedure
1. Provision infra from `infra/terraform` (`terraform apply`).
2. Restore Postgres from the latest snapshot + WAL (7-day PITR); prefer the cross-region copy if the primary region is down.
3. Restore Redis (persistence) or start cold (queues rebuild).
4. Point `DATABASE_URL`/`REDIS_URL`/`S3_BUCKET` at restored resources.
5. Run `prisma migrate deploy`, then `scripts/smoke-test.sh`.
6. Verify signing (HSM reachable) before resuming cert issuance.

## Drills
Quarterly: restore a prod snapshot to an isolated env + run smoke tests. Weekly 24h soak in staging.

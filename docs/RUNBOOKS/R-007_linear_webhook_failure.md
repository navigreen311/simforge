# R-007 — linear webhook failure

**Trigger:** Linear gap-ticket routing fails

## Response
Gaps continue to persist locally (dedup intact). Retry posting with exponential backoff. Page after 15 min of continued failure. Reconcile ticket ids once Linear recovers.

## Verify recovery
- Relevant Grafana dashboard is green; alert cleared in PagerDuty.
- `scripts/smoke-test.sh` passes.

## After-action
- File a post-incident note; if a process/context gap enabled it, update CLAUDE.md or the relevant command.

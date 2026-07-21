# R-003 — pdp latency spike

**Trigger:** PDP decision latency > 500ms p95

## Response
Check Redis health + PEP cache hit ratio. Temporarily enable PEP fail-open for non-compliance-adjacent action classes (Constitution-configured). Investigate slow policy queries; scale Redis if saturated.

## Verify recovery
- Relevant Grafana dashboard is green; alert cleared in PagerDuty.
- `scripts/smoke-test.sh` passes.

## After-action
- File a post-incident note; if a process/context gap enabled it, update CLAUDE.md or the relevant command.

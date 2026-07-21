# R-002 — sandbox tenant down

**Trigger:** A Forge sandbox tenant is unreachable

## Response
Fail over to the next-available Forge staging tenant. Throttle Packs that depend on the affected Forge. Open a Software Gap if the outage is a Forge defect. Resume normal routing once health checks pass.

## Verify recovery
- Relevant Grafana dashboard is green; alert cleared in PagerDuty.
- `scripts/smoke-test.sh` passes.

## After-action
- File a post-incident note; if a process/context gap enabled it, update CLAUDE.md or the relevant command.

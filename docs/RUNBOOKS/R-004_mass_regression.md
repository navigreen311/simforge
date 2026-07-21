# R-004 — mass regression

**Trigger:** > 10 scenarios flip to failing within 1h

## Response
Auto-activate safe-mode for the affected domain (POST /api/constitution/safe-mode). Investigate a shared cause: recent Forge release, model change, rubric change, or Village fingerprint drift. Do NOT issue new certs until root-caused.

## Verify recovery
- Relevant Grafana dashboard is green; alert cleared in PagerDuty.
- `scripts/smoke-test.sh` passes.

## After-action
- File a post-incident note; if a process/context gap enabled it, update CLAUDE.md or the relevant command.

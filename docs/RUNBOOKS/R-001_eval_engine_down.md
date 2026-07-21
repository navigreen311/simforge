# R-001 — eval engine down

**Trigger:** Eval engine error rate > 5%

## Response
Check rubric dimension failure distribution in Grafana (Eval Engine dashboard). Roll back the most recent rubric change if it correlates. Re-queue affected runs on the eval queue. Escalate to prompt-engineering if a specific dimension scorer throws.

## Verify recovery
- Relevant Grafana dashboard is green; alert cleared in PagerDuty.
- `scripts/smoke-test.sh` passes.

## After-action
- File a post-incident note; if a process/context gap enabled it, update CLAUDE.md or the relevant command.

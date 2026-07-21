# R-006 — village fingerprint drift

**Trigger:** Village schema fingerprint changed

## Response
Block all new cert issuance immediately. Alert Ivan + the Village OS maintainer. Manually review the structural diff (scripts/check-village-fingerprint.py). Only resume issuance after the new fingerprint is reviewed + recorded as current.

## Verify recovery
- Relevant Grafana dashboard is green; alert cleared in PagerDuty.
- `scripts/smoke-test.sh` passes.

## After-action
- File a post-incident note; if a process/context gap enabled it, update CLAUDE.md or the relevant command.

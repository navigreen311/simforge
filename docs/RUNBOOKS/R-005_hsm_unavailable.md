# R-005 — hsm unavailable

**Trigger:** HSM signing is unavailable

## Response
Pause all new CertSnapshot issuance (existing certs keep functioning). Fail over to the YubiHSM backup for emergency signing if approved. Two-person integrity required for any key operation. See docs/security.md key ceremony.

## Verify recovery
- Relevant Grafana dashboard is green; alert cleared in PagerDuty.
- `scripts/smoke-test.sh` passes.

## After-action
- File a post-incident note; if a process/context gap enabled it, update CLAUDE.md or the relevant command.

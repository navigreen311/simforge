# Security (blueprint §G)

## AuthN / AuthZ
- **User auth:** Clerk JWT (staging/prod). Dev uses `AUTH_MODE=dev-bypass` (full-access principal). Seam in `auth/clerk.py`.
- **Role-based authz on every endpoint** via `Depends(require_role(...))`. Roles: `admin`/`founder` (Ivan), `pack_owner`, `compliance_analyst`, `prompt_engineer`, `forge_owner`, `viewer`, `external_auditor`.
- **Ivan-only, audited:** cert issue/revoke, autonomy promote/demote, constitution ratify/veto, Pack ratification, safe-mode.
- Service-to-service: mutual TLS + short-lived service tokens (prod).

## Key management (signing)
- Prod root key in **AWS CloudHSM** (FIPS 140-2 Level 3); quarterly intermediates; emergency rotation → runbook R-005; CRL at `/api/attest/public-keys`. Two-person key ceremony (`docs/RUNBOOKS/KEY_CEREMONY.md`).
- Dev = local Ed25519 **StubSigner** (`signing-keys/`, git-ignored). Never in prod.

## PHI / PII
- **Synthetic only** — the Pack validator's PHI guard rejects SSN/DOB-shaped tokens; no real patient data ever enters a Pack or fixture.
- Evidence redaction classes (PHI-synthetic / financial / PII / standard) applied before external-auditor export.
- US-only data residency for v1; PHI evidence access is logged with accessor + reason.

## Secrets
- Dev: `.env` (git-ignored). Staging/prod: AWS Secrets Manager via IAM role.
- Never committed: signing private keys, HSM credentials, API keys, DB passwords, OAuth secrets. Terraform uses `REPLACE_VIA_SECRETS_MANAGER` placeholders.

## Audit
Governance-relevant actions (cert lifecycle, autonomy changes, amendments, Pack ratification, safe-mode, evidence access, signing) are recorded append-only and anchored to the Lineage graph.

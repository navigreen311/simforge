# ADR-0038 — Certificate Revocation List

**Status:** Accepted (2026-07-21).

## Context
`GET /api/attest/public-keys` published the signing key(s) but returned `crl: []` with a `WEEK 9`
placeholder. A signed `CertSnapshot` verifies cryptographically forever — so signature-valid is *not*
the same as still-honoured. A cert can be invalidated by a governance action (explicit revocation,
constitution-amendment auto-suspend, forge-drift suspend, training re-cert suspend) while its
signature stays valid. Without a published CRL, an external verifier that checks only the signature
would trust a revoked cert.

## Decision
- **`build_crl`** returns structured entries for every cert whose status is `revoked` or `suspended`,
  each carrying `cert_id`, `snapshot_id`, `forge_cap`, `status`, and the `reason` + `at` timestamp
  taken from the lifecycle event that invalidated it (newest first).
- **Expiry is excluded** — it is time-based and self-evident from `expiresAt`; the CRL carries only
  governance-invalidated certs.
- **Surface:** `GET /api/attest/public-keys` now populates `crl` with the revoked/suspended snapshot
  ids (the flat published list); `GET /api/attest/crl` returns the full structured list with reasons.

## Consequences
- An external verifier now does the complete check: signature valid **and** snapshot id not in the
  CRL. The CRL updates the moment any revoke/suspend path fires — all of which already route through
  the same `AgentCert.status` + `CertLifecycleEvent`, so the CRL needs no new bookkeeping.
- Suspended (temporary) certs appear alongside revoked (permanent) ones but are tagged by `status`, so
  a consumer can distinguish "gone" from "paused pending re-cert".
- Verified: issue → CRL empty → revoke → the cert's snapshot id appears in both `/public-keys` and the
  structured `/crl` with the correct reason and timestamp.

## Cross-references
Blueprint §C.3.14 (attestation). `src/services/cert/crl.py`, ADR-0007 (signed snapshots), ADR-0017 /
ADR-0020 / ADR-0026 (the suspend/revoke paths whose certs land in the CRL).

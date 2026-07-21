# Key Ceremony (blueprint §G.2)

Root signing key operations require **two-person integrity** (Ivan + witness).
- Root key: AWS CloudHSM, FIPS 140-2 Level 3.
- Intermediates derived quarterly; used for day-to-day CertSnapshot signing.
- Emergency rotation on compromise (runbook R-005). Publish updated CRL to /api/attest/public-keys.
- Dev uses a local Ed25519 StubSigner (signing-keys/, git-ignored) — NEVER in prod.

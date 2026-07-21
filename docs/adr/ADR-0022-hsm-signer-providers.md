# ADR-0022 — YubiHSM / CloudHSM signer providers

**Status:** Accepted (2026-07-21).

## Context
ADR-0018 shipped `stub` (dev auto-gen) and `file` (prod, secret-injected PEM) signers, leaving
`HSM_PROVIDER=yubihsm|cloudhsm` raising `NotImplementedError`. The blueprint (§C.12) targets a
YubiHSM in staging and AWS CloudHSM in prod so the signing private key never leaves the hardware.
Neither device nor its vendor SDK/credentials are available in this environment, so the goal is
**ready-to-activate** integration code — structurally complete and unit-testable — that turns on the
moment the SDK + a reachable HSM + credentials exist, without shipping half-working stubs.

## Decision
- **Backend-agnostic signer** — `HsmEd25519Signer(Signer)` (`services/cert/hsm_signer.py`) holds no
  private key; it delegates `sign` to an `HsmBackend` (on-device) and derives `verify` /
  `public_key_pem` / `key_id` from the backend's public key. Every HSM shares this one class, so the
  logic that matters is tested once.
- **`HsmBackend` protocol** — `sign(payload) -> bytes` + `public_key_der() -> bytes` (Ed25519
  SubjectPublicKeyInfo). A YubiHSM, a PKCS#11 HSM, or a test fake all satisfy it.
- **Concrete backends** (lazy SDK import): `_YubiHsmBackend` (the `yubihsm` SDK — connector →
  session → on-device Ed25519 key → `sign_eddsa`) and `_Pkcs11Backend` (the `pkcs11` SDK / vendor
  `.so` — token → session → EDDSA sign, for AWS CloudHSM or any PKCS#11 HSM). Each raises a clear
  `SignerConfigError` naming the missing SDK or config, rather than crashing.
- **Dispatch** — `get_signer` now resolves `yubihsm`/`cloudhsm` to these builders; a genuinely
  unknown provider still raises `NotImplementedError`. Optional deps live under the `hsm` extra
  (`yubihsm[http]`, `python-pkcs11`) — **not** pulled by dev/CI.

## Consequences
- The signing seam is complete for all four providers behind one `Signer` ABC. Activating a real
  HSM is config + `pip install '.[hsm]'` + a reachable device — no code change.
- What can/can't be verified here: the **shared** signer logic (sign/verify/public-key/key-id via a
  fake Ed25519 backend) and the **dispatch + SDK-missing guards** for both providers are unit-tested;
  the vendor connection code itself needs real hardware and is exercised at deploy time. This is the
  honest boundary — the untested surface is the thin per-vendor wrapper, not the crypto logic.
- CertSnapshot signing/verification is unchanged (Ed25519 throughout), so certs signed by an HSM
  verify through the same `verify_snapshot` path.

## Cross-references
Blueprint §C.12 (signing; YubiHSM/CloudHSM), ADR-0018 (stub/file signers + `Signer` ABC + dispatch),
ADR-0007 (cert snapshot signing round-trip).

# ADR-0018 — Real Clerk JWT auth + production Ed25519 signer

**Status:** Accepted (2026-07-21).

## Context
Auth and signing shipped as seams (ADR-0001): `AUTH_MODE=dev-bypass` yielded a fixed admin
principal and `auth/clerk.py` raised `NotImplementedError`; `HSM_PROVIDER=stub` used a `StubSigner`
that **auto-generates** a local Ed25519 key. Both are correct for dev but are not deployable — the
Clerk path was unimplemented, and a production deploy of the stub signer would silently mint an
untrusted signing key. No real Clerk instance or HSM credentials are available here, so the goal is
production-ready code paths that default off and are proven hermetically.

## Decision
### Clerk JWT verification (`AUTH_MODE=clerk`)
- **`auth/clerk.py`** now verifies a real Clerk RS256 JWT (PyJWT + `cryptography`, added dep
  `pyjwt[crypto]`): parse the Bearer token, resolve the signing key, verify the RS256 signature,
  and check `exp`/`iat` (+ optional `iss`/`aud`). Key resolution: `CLERK_JWKS_JSON` (static JWKS,
  offline/test) → else `CLERK_JWKS_URL` (Clerk's live JWKS, fetched + cached via `PyJWKClient`).
- **`auth/roles.py`** maps claims → SimForge roles from `roles` / `public_metadata.roles` /
  `org_role` (Clerk B2B, `org:admin` → `admin`), keeping only recognized roles.
- **`get_current_principal`** dispatches on `AUTH_MODE`: `dev-bypass` (default) → fixed principal;
  `clerk` → `verify_clerk_token(Authorization)`. Every 401 is an `HTTPException`, so call sites and
  `require_role` are unchanged.

### Production signer (`HSM_PROVIDER=file`)
- **`FileEd25519Signer`** loads an **existing** Ed25519 key from a secret-manager-injected PEM
  (`SIMFORGE_SIGNING_PRIVATE_KEY_PEM`) or a file path, and **never auto-generates** — a
  misconfigured prod deploy fails loudly (`SignerConfigError`) instead of minting an untrusted key.
- **`get_signer`** dispatches on `HSM_PROVIDER`: `stub` (dev, auto-gen) | `file` (prod Ed25519,
  require key) | `yubihsm`/`cloudhsm` (real HSMs — drop in behind the same `Signer` ABC once the
  vendor SDK + creds exist; raise until then). `reset_signer_cache()` added for tests.

Defaults are unchanged: `AUTH_MODE=dev-bypass` + `HSM_PROVIDER=stub`, so dev/CI stay offline and
deterministic.

## Consequences
- SimForge is deployable with real auth (point `AUTH_MODE=clerk` + `CLERK_JWKS_URL` at a Clerk
  instance) and a real, secret-injected signing key (`HSM_PROVIDER=file` +
  `SIMFORGE_SIGNING_PRIVATE_KEY_PEM`) — no code change, config only.
- Verified live: `AUTH_MODE=clerk` app rejects missing/garbage tokens (401) and accepts a valid
  self-issued RS256 token (200); `FileEd25519Signer` round-trips sign/verify through `get_signer`.
- YubiHSM/CloudHSM remain the only unimplemented signer providers (need vendor SDK + credentials);
  the `Signer` ABC is their drop-in point.

## Cross-references
Blueprint §G.1 (auth/roles), §C.12 (signing), ADR-0001 (stub-first seams), ADR-0007 (cert snapshots
consume the signer).

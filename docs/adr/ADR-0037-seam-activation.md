# ADR-0037 — Seam-activation tooling + live Forge activation

**Status:** Accepted (2026-07-21).

## Context
Every external integration was built as a config-gated seam (ADR-0030), and `/api/health/config`
reports each seam's *mode*. What was missing was a way to answer the operational question at deploy
time: "is this activated seam actually **working** — is the collector reachable, the key loadable, the
sandbox up?" And of the seams, one has a runnable provider on a dev box (the Forge HTTP sandbox) yet
had never been activated end-to-end here — the code path (`FORGE_MODE=http`) was only exercised via an
injected ASGI transport in tests, never over a real socket.

## Decision
- **`scripts/verify-seams.py`** — a deploy-readiness verifier that probes every seam that is
  *activated* and reports `ok` / `stub` / `FAIL`: Clerk JWKS fetch, signer-key load, each Forge
  `/health`, the LLM daemon/key, Linear config, Redis ping, OTLP reachability. Hermetic by default (an
  all-stub deployment is all `stub`, exit 0); exits non-zero **only** when an activated seam is broken,
  so CI/deploy can gate on it. `auto` LLM degrading to stub is correctly *not* a failure.
- **`scripts/run-forge-sandbox.py`** — a runnable reference Forge sandbox serving all six forges (each
  `create_reference_sandbox(forge)` mounted under `/{forge}`), so the HTTP Forge seam can be activated
  locally with no third party. Fulfils the runner its docstring had long promised.
- **`docs/RUNBOOKS/seam-activation.md`** — how to flip each seam to a real system and confirm it, with
  the fully-runnable HTTP-Forge activation recipe.

## Consequences: the HTTP Forge seam is now genuinely activated (verified live)
Not just wired — run for real on this box: the reference sandbox served all six forges over HTTP;
the API booted `FORGE_MODE=http` with a per-forge `FORGE_SANDBOX_URLS`; `verify-seams` reported
`forges → ok` (6/6 reachable, 0 broken); `/api/health/config` showed `forge_mode: http`; and
`scn.gs.crisis.003` ran end-to-end, emitting three `forge_fault` trace events (cre-forge, voiceforge,
vaf) resolved through **real HTTP** to the sandbox — the exact production path, minus a vendor.

- Because the Forge contract is Pact-pinned (ADR-0036), swapping the reference server for a real
  vendor sandbox is a URL change, not a code change.
- The remaining seams' *providers* (live Clerk, HSM hardware, a production Forge, Tempo, Linear, real
  Village OS, cloud `terraform apply`) can't run on a dev box, but they activate through the identical
  flow — flip the env, run `verify-seams`, confirm `ok`. The honest boundary is provisioning those
  systems + supplying credentials; every seam on the SimForge side is wired, health-checked, and
  contract-pinned.

## Cross-references
ADR-0030 (seams + `/api/health/config`), ADR-0016 (HTTP Forge adapter + reference sandbox), ADR-0036
(Forge Pact), `docs/RUNBOOKS/seam-activation.md`, `docs/deploy.md` (seam matrix).

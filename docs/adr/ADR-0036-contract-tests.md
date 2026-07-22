# ADR-0036 — Consumer-driven contract tests (Pact)

**Status:** Accepted (2026-07-21).

## Context
Two integration boundaries were only ever exercised end-to-end, never pinned by a *contract*: the
**Forge sandbox** HTTP API (`HttpForgeAdapter` ↔ a real Forge sandbox, ADR-0016) and **village_bridge**
(`VillageReader` ↔ the VillageData layout). The blueprint lists Pact-style contract tests as a v1.1
deferral, and `contract-tests.yml` had a placeholder that swallowed failures
(`pytest tests/contract || echo "no contract tests yet"`). Without a contract, a Forge vendor could
change a response field, or the Village layout could shift, and nothing would fail until a live run
broke.

## Decision
- **Forge boundary → real Pact.** Using `pact-python` (v3, Rust FFI — no broker, no Ruby), a
  consumer-driven contract with two hermetic halves:
  1. *Consumer* — `HttpForgeAdapter` drives a Pact mock provider on localhost, proving it sends the
     contracted requests (`GET /version`, `POST /sandbox/tenants`, `POST /…/exercise`) and parses the
     contracted responses. This writes the pact file (`tests/contract/pacts/`, committed).
  2. *Provider* — the `reference_sandbox` FastAPI app (the conformant reference every real Forge must
     match) is driven in-process through the same API, proving it honours the contracted response
     shapes. A cross-check asserts every pact interaction maps to a provider endpoint.
- **Village boundary → filesystem contract.** Pact is HTTP-oriented; the Village boundary is a
  directory shape, so its consumer-driven contract is structural + shape assertions against the
  reference provider (the committed VillageData fixture): every framework `VillageReader` reads is
  provided as the contracted type, and the structural fingerprint is deterministic. Artifact:
  `pacts/village_bridge.contract.json`.
- **CI now gates.** The `contract-tests.yml` escape hatch is removed — the job runs
  `pytest tests/contract` for real; `pact-python` is a dev dependency.

## Consequences
- A breaking change on *either* side of the Forge contract fails CI: if the adapter stops sending a
  contracted field, or the reference sandbox stops returning one, the paired tests catch it. Same for
  the Village layout.
- Fully hermetic: the Pact mock binds localhost, the provider is in-process ASGI, the Village provider
  is a fixture — no broker, no network, no live Forge.
- Deploy-time extension (not needed here): publish the committed pact to a Pact Broker and run
  `pact-python`'s provider verification against a live Forge sandbox in staging. The contract artifact
  is already in the right shape for that.

## Cross-references
Blueprint §L.4 (contract tests, v1.1), §E.1 (the Forge sandbox API). `apps/api/tests/contract/`,
ADR-0016 (the HTTP Forge adapter + reference sandbox this pins), `.github/workflows/contract-tests.yml`.

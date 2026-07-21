# ADR-0016 — HTTP-backed Forge adapter + uniform `exercise` op + mode selection

**Status:** Accepted (2026-07-21).

## Context
ADR-0010–0015 shipped all six Forges as **Local** in-process adapters behind the `ForgeAdapter`
contract. Every one of those ADRs promised "a real sandbox drops in as an HTTP-backed adapter
behind the same contract" — but no such adapter existed, and the scenario runner drove each Local
adapter through **forge-specific** ops (`emd_release`, `generate_and_extract`, `place_and_handle`,
…) via per-forge helpers + `cast(LocalX, ...)`. So the contract was real but the swap was
aspirational, and the runner was hard-coded to Local.

## Decision
1. **Uniform `exercise` op on the contract.** Added `async def exercise(tenant_id, cap, fault_type)
   -> dict` (returns `{outcome, fault?}`) to `ForgeAdapter`. Each Local adapter implements it as a
   thin wrapper over its existing combined op; the HTTP adapter implements it over the wire. The
   runner now drives **every** forge through this one method — no per-forge helpers, no casts.
2. **`HttpForgeAdapter`** (`services/forges/http_adapter.py`) — implements the full contract against
   a real sandbox over HTTP (generic sandbox API: `/health`, `/version`, `/sandbox/tenants` +
   `/{id}/{seed-state,audit-log,faults,exercise}`). Injectable `httpx` transport for hermetic tests.
3. **Mode selection** (`config.py` + `registry.py`). `FORGE_MODE` (`local` default | `http`) +
   `FORGE_SANDBOX_URLS` (`"name=url,…"`). `get_forge_adapter` returns `HttpForgeAdapter` when mode
   is `http` **and** a URL is configured for that forge; otherwise the Local adapter. Selection is
   **per-forge** — some forges can be HTTP while others stay Local in the same run. `local_forge_
   adapter` exposes the Local adapter regardless of mode (used by the reference sandbox). Default
   stays Local → dev/CI remain deterministic and offline.
4. **Reference sandbox** (`services/forges/reference_sandbox.py`) — a conformant FastAPI
   implementation of the generic sandbox API, backed by the Local engine, so (a) `HttpForgeAdapter`
   is tested hermetically via an ASGI transport (HTTP → engine → HTTP, no network), and (b)
   `scripts/run-forge-sandbox.py` serves a real stand-in a dev can point `FORGE_MODE=http` at.
5. **Runner collapse.** The six `_run_<forge>` helpers + `_BANK_FAULT`/`_CONSOLE_FAULT`/
   `_FUNNEL_FAULT` became one `_run_forge_side_effects` loop: group caps by forge → resolve adapter
   → `exercise` each cap → emit trace. The runner's only remaining forge-specific knowledge is the
   fault-selection policy (`_FORGE_MODULE_FAULT` + `_FORGE_DEFAULT_FAULT`) — *which* fault to
   inject; *how* to exercise lives in the adapter.

## Consequences
- The real-sandbox swap is now real: point `FORGE_MODE=http` + `FORGE_SANDBOX_URLS` at a sandbox and
  SimForge provisions/exercises/inspects it over HTTP — including `get_current_version`, which feeds
  **CertSnapshot version-pinning**, so certs can pin the real Forge's version.
- The runner is forge-agnostic and mode-agnostic; adding a seventh forge no longer touches it.
- Verified live: a reference CapitalForge sandbox on `:9101`, main API with `FORGE_MODE=http`
  → `/api/forges/capitalforge/health` crosses HTTP (mode `http`), and `scn.gs.buy.002` drives
  `POST /sandbox/tenants` → `/exercise` → `DELETE` on the sandbox, surfacing `capitalforge/emd
  fraud_flag` → a Software Gap — while `cre-forge` (no URL) stayed Local in the same run (mixed mode).

## Cross-references
Blueprint §E.1 (contract/endpoints), ADR-0010–0015 (the six Local Forges), ADR-0001 (stub-first),
ADR-0007 (cert version-pinning consumes `get_current_version`).

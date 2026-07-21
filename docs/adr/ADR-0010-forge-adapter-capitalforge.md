# ADR-0010 — Forge adapter contract + CapitalForge (Mock Bank)

**Status:** Accepted (2026-07-21).

## Context
v1 had no Forge integration layer — the scenario runner used a pure in-process mock world, and
Software Gaps were tier/outcome **heuristics**, not real Forge faults. The blueprint (Part E)
defines a `ForgeAdapter` contract and names **CapitalForge = the Mock Bank** (§E.7).

## Decision
- **`ForgeAdapter` ABC** (`services/forges/base.py`): `health_check`, `provision_sandbox_tenant`,
  `teardown_sandbox_tenant`, `seed_state`, `get_audit_log`, `get_current_version`, `inject_fault`
  + `SandboxTenant` / `Fault` / `FaultType`. `NullForgeAdapter` for Forges not yet wired
  (reports unhealthy, refuses provisioning).
- **CapitalForge (Mock Bank)** — the first real adapter, **in-process + deterministic**
  (`mock_bank.py` engine + `LocalCapitalForgeAdapter`). Tenants, accounts, `apply/wire/emd_release`,
  fault injection (declination/fraud_flag/nsf/ofac/velocity), audit log. Same stub-first
  philosophy as ADR-0001; a real CapitalForge sandbox drops in as an HTTP-backed adapter behind
  the same contract.
- **Registry/factory** (`get_forge_adapter`) resolves a forge name → adapter; only CapitalForge is
  real in v1.
- **Runner wiring**: for capitalforge scenarios the runner provisions a sandbox tenant, runs the
  tested bank op, and records `forge_action` / `forge_fault` **trace events** (a fault is injected
  deterministically on even `seed` so the fault path is exercised; real faults come from a live
  Forge). Sandbox-isolated — **no Village writes**.
- **Real Software Gaps**: `detect_forge_fault_gaps` turns `forge_fault` trace events into gaps
  (forge/module/severity/reason), merged with the existing heuristic candidates and deduped.
- **Router** `/api/forges` — list/health + a CapitalForge demo flow.

## Consequences
- Gaps for capitalforge scenarios now reflect **actual runtime faults**, not just tier heuristics.
- The `ForgeAdapter` contract is the seam for the other 5 Forges (VoiceForge, VAF, medlink-pro,
  CRE-Forge, FunnelForge) and for swapping the local Mock Bank for a real HTTP sandbox.
- Contract test (blueprint §I.3) guards the adapter shape + sandbox isolation.

## Cross-references
Blueprint Part E (§E.1 contract, §E.7 CapitalForge), §C.11 (reporter), §I.3 (contract testing),
ADR-0001 (stub-first).

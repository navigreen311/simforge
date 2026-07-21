# ADR-0025 — Integrated (write-enabled) execution

**Status:** Accepted (2026-07-21). **Deliberately relaxes the sandbox-only guardrail (ADR-0001)**
for a specific, gated feature.

## Context
Every prior increment was sandbox-only and read-only against the Village (ADR-0001; reinforced in
each PR). That was the right default while the certification loop was being proven. The blueprint
defers **integrated (write-enabled) execution** to v1.1/v1.2 (§L.4): a run that doesn't merely
*simulate* an agent's actions but *commits* them. This is the feature that turns a certified agent's
authority into real effect. The owner has explicitly authorized building it.

## What "integrated" means here
There is **no** real Village or production Forge in this environment (ADR-0001) — so this is not
"write to a live external system" (there isn't one). It implements the write-enabled execution mode
*within the platform*: for the capabilities an agent exercised, decide (via the PDP) whether the
agent may act, and record the outcome as an auditable, reversible **effect ledger**.

## Decision — safety by construction
1. **Triple-gated, off by default.** A run executes integrated actions only when **all three** hold:
   `INTEGRATED_EXECUTION_ENABLED` (global flag, default **false**), the pack opts in
   (`integratedRunsAllowed`), and the run explicitly requests it (`?integrated=true`). Any gate
   unmet → the run is sandboxed. No surprise writes; the shipped default changes nothing.
2. **PDP-gated per action.** Each tested capability is run through `PDP.decide` (ADR-0024). Only an
   `allow` is **applied**; `deny` / `step_up` / `downgrade` are **blocked** (recorded, not applied).
   An uncertified, suspended, revoked, or low-autonomy agent therefore cannot execute anything — the
   governance layer is the gate.
3. **The read-only VillageData fixture is never written.** Effects are persisted as `TraceEvent`s
   (`integrated_action` / `integrated_revert`), so the ledger is queryable and isolated.
4. **Auditable + reversible.** Every applied action is a ledger entry carrying the PDP decision +
   reason; `POST /api/execution/run/{run}/actions/{id}/revert` writes a compensating entry. Blocked
   actions cannot be reverted (nothing happened).
5. **Observable.** `GET /api/execution/status` reports whether the deployment has it enabled; the
   ledger is visible at `GET /api/execution/run/{run}/actions`.

## Consequences
- Certification becomes *consequential*: a certified L4/L5 agent's action is applied; an
  uncertified agent's identical action is blocked, in the same run — proven end-to-end.
- The guardrail is relaxed **narrowly and reversibly**: turning the flag off (the default) restores
  full sandbox-only behavior with no code change. CI runs entirely with the flag off.
- Still no integrated writes to any real external system (none exist); the effect ledger is the
  extent of "the write." When real Forges/Village are wired, an `allow` here is the point at which
  their write API would be called — behind the same PDP gate.

## Cross-references
Blueprint §L.4 (integrated execution deferral), §B (executionMode/narrativeMode), ADR-0001
(sandbox-first — this narrows it), ADR-0024 (PDP — the gate that makes this safe), ADR-0017/0020
(drift-suspend / reinstate, which flip whether an action is allowed).

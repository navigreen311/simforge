# ADR-0014 — Fifth real Forge: medlink-pro (Clinical Console)

**Status:** Accepted (2026-07-21).

## Context
ADR-0010–0013 wired CapitalForge, VAF, VoiceForge, and CRE Forge behind the `ForgeAdapter`
contract, proving the N-forge runner dispatch across banking, documents, telephony, and CRE deals.
`medlink-pro` (the healthcare-staffing venture Forge, blueprint §E.4) was the last Null adapter
whose caps are already exercised by seeded scenarios — the `pack.medlink-pro.v1` pack has three
scenarios testing `medlink-pro.scheduler.*` / `medlink-pro.compliance.*` caps (e.g.
`scn.ml.place.002`, tested agent `jennifer_adams`). Its distinctive surface is **UI-fault
injection** plus scheduler/compliance/clinician state, and it is **PHI-adjacent** — fixtures must
be synthetic.

## Decision
- **Clinical Console engine** (`services/forges/clinical_console.py`) — an in-process, deterministic
  sandbox that seeds a **PHI-synthetic** staffing tenant (scheduler/compliance/clinician state),
  injects UI + staffing faults, and "runs" a console task, surfacing any injected fault. Fixtures
  are synthetic only (`"SYNTHETIC CLINICIAN"`/`"SYNTHETIC FACILITY"`) — **never real PHI**. Fault
  menu spans **compliance/safety** (`credential_expired_unflagged`, `shift_double_booked`,
  `phi_overexposure` → **P0**) and **UI/state** (`ui_blocking_modal`, `stale_roster`,
  `timecard_missing`, `msa_terms_stale` → **P1**).
- **`LocalMedLinkProAdapter`** (`services/forges/medlink_pro.py`) — implements the `ForgeAdapter`
  contract (version `medlink-pro.console.v1`), backed by the Clinical Console engine, plus a
  forge-specific `start_and_run` op. A real medlink-pro sandbox drops in as an HTTP-backed adapter
  behind the same contract (stub-first, ADR-0001).
- **Registry** resolves `"medlink-pro"` → `LocalMedLinkProAdapter`; only `funnelforge` stays
  `NullForgeAdapter`.
- **Runner** — added `_run_medlink_pro` to the per-forge dispatch, with a per-module fault map
  (`_CONSOLE_FAULT`: `scheduler` → `shift_double_booked`, `compliance`/`clinician` →
  `credential_expired_unflagged`, else `ui_blocking_modal`) — mirroring CapitalForge's
  `_BANK_FAULT`. Same `forge_action`/`forge_fault` trace events; the reporter is already
  forge-agnostic, so medlink-pro faults become real Software Gaps with no reporter change.
  Sandbox-isolated — **no Village writes**.
- **Router** — `POST /api/forges/medlink-pro/demo` mirrors the other demos.

## Consequences
- The `pack.medlink-pro.v1` staffing scenarios now surface **real console faults** (a double-booked
  shift, an unflagged expired credential, a blocking UI modal) → real Software Gaps, instead of tier
  heuristics.
- **5 of 6 Forges are real**; only `funnelforge` (§E.6, lead/campaign/sequence) remains Null.

## Cross-references
Blueprint §E.4 (medlink-pro), §E.1 (contract), §C.11 (reporter), §I.3 (contract testing),
ADR-0010 (CapitalForge / the pattern + `_BANK_FAULT`), ADR-0011/0012/0013 (VAF/VoiceForge/CRE),
ADR-0001 (stub-first).

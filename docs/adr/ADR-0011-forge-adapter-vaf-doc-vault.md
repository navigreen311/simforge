# ADR-0011 — Second real Forge: VisionAudioForge (VAF) Doc Vault

**Status:** Accepted (2026-07-21).

## Context
ADR-0010 shipped the `ForgeAdapter` contract and the first real Forge (CapitalForge = Mock Bank),
proving the fault→gap loop. Only 1 of the 6 Forges was real, so document-processing scenarios
(license/credential/title verification) could not surface real document faults — the crisis
scenario `scn.gs.crisis.003` (a title defect before closing) had no VAF signal. The blueprint
(§E.3) names **VisionAudioForge = document + audio intelligence** with a document-fault menu.

## Decision
- **VAF Doc Vault engine** (`services/forges/doc_vault.py`) — an in-process, deterministic sandbox
  that generates **synthetic** documents (never real PHI — fixtures are `"SYNTHETIC PERSON"`),
  injects document faults, and "OCR-extracts" fields, surfacing any injected fault. Fault menu
  (§E.3) with severities: `forged_signature`/`revoked_license`/`oig_match` → **P0**;
  `expired_date`/`name_dob_mismatch`/`altered_amount` → **P1**; `missing_pages` → **P2**.
- **`LocalVAFAdapter`** (`services/forges/visionaudioforge.py`) — implements the same
  `ForgeAdapter` contract (version `vaf.docvault.v1`), backed by the Doc Vault engine, plus
  forge-specific ops (`generate_and_extract`, `prosody_score`). A real VAF sandbox drops in as an
  HTTP-backed adapter behind the same contract (stub-first, ADR-0001).
- **Registry** resolves `"vaf"` → `LocalVAFAdapter`; `voiceforge`/`medlink-pro`/`cre-forge`/
  `funnelforge` stay `NullForgeAdapter` until wired.
- **Runner generalized** — `_run_capitalforge_side_effects` became `_run_forge_side_effects`,
  dispatching per-forge (`_run_capitalforge` + `_run_vaf`). The fault trigger widened from
  even-`seed` to **`tier == "advanced_crisis"` OR even `seed`**, so crisis scenarios always
  exercise the fault path. Both emit the same `forge_action`/`forge_fault` trace events; the
  reporter's `detect_forge_fault_gaps` is already forge-agnostic, so VAF faults become real
  Software Gaps with no reporter change. Sandbox-isolated — **no Village writes**.
- **Scenario** `scn.gs.crisis.003` gains `vaf.doc_vault.retrieve` in `tested_forge_caps`, so the
  seeded `david_kim` crisis run surfaces a forged-signature fault on the title document.
- **Router** — `POST /api/forges/vaf/demo` mirrors the CapitalForge demo.

## Consequences
- Document-processing scenarios now surface **actual document faults**, not tier heuristics.
- 4 of 6 Forges remain `NullForgeAdapter`; the contract + registry + runner dispatch are the seam
  for wiring them (and for swapping the local Doc Vault for a real HTTP VAF sandbox).
- The runner's forge dispatch is now N-forge (loop over caps grouped by forge), not
  CapitalForge-special-cased.

## Cross-references
Blueprint §E.3 (VisionAudioForge), §E.1 (contract), §C.11 (reporter), §I.3 (contract testing),
ADR-0010 (CapitalForge / the pattern this follows), ADR-0001 (stub-first).

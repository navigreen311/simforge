# ADR-0012 — Third real Forge: VoiceForge (Call Center)

**Status:** Accepted (2026-07-21).

## Context
ADR-0010 (CapitalForge Mock Bank) and ADR-0011 (VAF Doc Vault) proved the fault→gap loop and the
N-forge runner dispatch. 3 of 6 Forges remained `NullForgeAdapter`. The crisis scenario
`scn.gs.crisis.003` already declared `voiceforge.call_center.inbound` in `tested_forge_caps`, but
with VoiceForge unwired that cap produced no runtime signal. The blueprint (§E.2) defines
VoiceForge's surface as **line-quality control + persona injection + call events**.

## Decision
- **Call Center engine** (`services/forges/call_center.py`) — an in-process, deterministic sandbox
  that places synthetic calls against a persona catalog (§E.2 preload), injects call faults, and
  "handles" a call, surfacing any injected fault. Fault menu spans **line-quality**
  (`dropped_call`, `dead_air`, `line_noise`), **call-flow** (`misroute`, `hold_timeout`,
  `escalation_failure`), and **compliance** (`disclosure_missing`). Severities:
  `dropped_call`/`escalation_failure`/`disclosure_missing` → **P0**; the rest → **P1**.
- **`LocalVoiceForgeAdapter`** (`services/forges/voiceforge.py`) — implements the same
  `ForgeAdapter` contract (version `voiceforge.callcenter.v1`), backed by the Call Center engine,
  plus forge-specific ops (`place_and_handle`, `prosody_score`). A real VoiceForge sandbox drops
  in as an HTTP/WebSocket-backed adapter behind the same contract (stub-first, ADR-0001).
- **Registry** resolves `"voiceforge"` → `LocalVoiceForgeAdapter`; `medlink-pro`/`cre-forge`/
  `funnelforge` stay `NullForgeAdapter` until wired.
- **Runner** — added `_run_voiceforge` to the per-forge dispatch in `_run_forge_side_effects`
  (alongside `_run_capitalforge` + `_run_vaf`). The cap's third segment selects call direction
  (`voiceforge.call_center.inbound` → inbound). Same `forge_action`/`forge_fault` trace events;
  the reporter is already forge-agnostic, so VoiceForge faults become real Software Gaps with no
  reporter change. Sandbox-isolated — **no Village writes**.
- **Router** — `POST /api/forges/voiceforge/demo` mirrors the CapitalForge/VAF demos.

## Consequences
- `scn.gs.crisis.003` now surfaces **both** a VAF document fault and a VoiceForge call fault in one
  run — the crisis exercises document + telephony surfaces together, as intended.
- 3 of 6 Forges are real; 3 remain `NullForgeAdapter` (`medlink-pro`, `cre-forge`, `funnelforge`),
  wired the same way when their turn comes.
- The runner dispatch pattern (loop caps grouped by forge → per-forge helper) is now proven across
  three distinct Forge domains (banking, documents, telephony).

## Cross-references
Blueprint §E.2 (VoiceForge), §E.1 (contract), §C.11 (reporter), §I.3 (contract testing),
ADR-0010 (CapitalForge / the pattern this follows), ADR-0011 (VAF), ADR-0001 (stub-first).

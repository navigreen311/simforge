# ADR-0013 — Fourth real Forge: CRE Forge (Deal Desk)

**Status:** Accepted (2026-07-21).

## Context
ADR-0010/0011/0012 wired CapitalForge, VAF, and VoiceForge behind the `ForgeAdapter` contract,
proving the N-forge runner dispatch across banking, documents, and telephony. The crisis scenario
`scn.gs.crisis.003` ("title defect surfaces days before closing") declared **three** forge caps —
`cre-forge.deals.title`, `voiceforge.call_center.inbound`, `vaf.doc_vault.retrieve` — but with CRE
Forge unwired, `cre-forge.deals.title` produced no runtime signal, even though a **title defect on
a deal** is the literal subject of the scenario. The blueprint (§E.5) defines CRE Forge's surface
as lead/deal/buyer state seeding + sequence triggers + audit log.

## Decision
- **Deal Desk engine** (`services/forges/deal_desk.py`) — an in-process, deterministic sandbox that
  seeds synthetic CRE deals (`assignment`/`wholesale`/`double_close`/`novation`), injects deal
  faults, and "processes" a deal, surfacing any injected fault. Fixtures are synthetic only
  (`"SYNTHETIC BUYER"`/`"SYNTHETIC SELLER"`). Fault menu spans **deal** (`title_defect`,
  `lien_undisclosed`, `assignment_blocked`, `deal_stale`), **buyer** (`buyer_unresponsive`), and
  **lead/sequence** (`sequence_stall`, `duplicate_lead`). Severities: `title_defect`/
  `lien_undisclosed`/`assignment_blocked` → **P0**; `deal_stale`/`buyer_unresponsive`/
  `sequence_stall` → **P1**; `duplicate_lead` → **P2**.
- **`LocalCREForgeAdapter`** (`services/forges/cre_forge.py`) — implements the same `ForgeAdapter`
  contract (version `cre-forge.dealdesk.v1`), backed by the Deal Desk engine, plus a forge-specific
  `create_and_process` op. A real CRE Forge sandbox drops in as an HTTP-backed adapter behind the
  same contract (stub-first, ADR-0001).
- **Registry** resolves `"cre-forge"` → `LocalCREForgeAdapter`; `medlink-pro`/`funnelforge` stay
  `NullForgeAdapter` until wired.
- **Runner** — added `_run_cre_forge` to the per-forge dispatch in `_run_forge_side_effects`. On
  fault, injects `title_defect` (P0) — exactly the crisis scenario's premise. Same
  `forge_action`/`forge_fault` trace events; the reporter is already forge-agnostic, so CRE Forge
  faults become real Software Gaps with no reporter change. Sandbox-isolated — **no Village writes**.
- **Router** — `POST /api/forges/cre-forge/demo` mirrors the other demos.

## Consequences
- `scn.gs.crisis.003` now surfaces **all three** of its declared forge faults in a single run — a
  CRE title defect, a VAF forged signature, and a VoiceForge dropped call — fully exercising the
  crisis's document + telephony + deal surfaces together.
- **4 of 6 Forges are real**; 2 remain `NullForgeAdapter` (`medlink-pro`, `funnelforge`), wired the
  same way when their turn comes.

## Cross-references
Blueprint §E.5 (CRE Forge), §E.1 (contract), §C.11 (reporter), §I.3 (contract testing),
ADR-0010 (CapitalForge / the pattern), ADR-0011 (VAF), ADR-0012 (VoiceForge), ADR-0001 (stub-first).

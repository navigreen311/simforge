# ADR-0015 — Sixth (final) real Forge: FunnelForge (Flows)

**Status:** Accepted (2026-07-21).

## Context
ADR-0010–0014 wired CapitalForge, VAF, VoiceForge, CRE Forge, and medlink-pro behind the
`ForgeAdapter` contract. `funnelforge` (the marketing/CRM funnel-automation Forge, blueprint §E.6)
was the **last** Null adapter. Its `funnelforge.sequences.trigger` cap is already declared by
`scn.ml.place.002` (tested agent `jennifer_adams`), so wiring it both completes the set and rides
an existing scenario for a live fault→gap signal.

## Decision
- **Funnel engine** (`services/forges/funnel.py`) — an in-process, deterministic sandbox that seeds
  synthetic leads/segments/campaigns/sequences, injects flow faults, and "runs" a flow, surfacing
  any injected fault. Fixtures are synthetic only (`"SYNTHETIC LEAD"`/`"SYNTHETIC CAMPAIGN"`). Fault
  menu spans **delivery/compliance** (`webhook_dropped`, `campaign_to_unsubscribed` → **P0**) and
  **flow/data** (`sequence_misfire`, `segment_stale`, `bounce_unhandled`, `lead_misattributed` →
  **P1**; `duplicate_enrollment` → **P2**).
- **`LocalFunnelForgeAdapter`** (`services/forges/funnelforge.py`) — implements the `ForgeAdapter`
  contract (version `funnelforge.flows.v1`), backed by the Funnel engine, plus a forge-specific
  `trigger_and_run` op. A real FunnelForge sandbox drops in as an HTTP + webhook-backed adapter
  behind the same contract (stub-first, ADR-0001).
- **Registry** now resolves **all six** Forge names to real Local adapters; `NullForgeAdapter` is
  retained only as the fallback for **unknown** forge names.
- **Runner** — added `_run_funnelforge` to the per-forge dispatch, with a per-module fault map
  (`_FUNNEL_FAULT`: `leads` → `webhook_dropped`, `campaigns` → `campaign_to_unsubscribed`,
  `sequences` → `sequence_misfire`, `segments` → `segment_stale`, else `webhook_dropped`). Same
  `forge_action`/`forge_fault` trace events; the reporter is already forge-agnostic. Sandbox-
  isolated — **no Village writes**.
- **Router** — `POST /api/forges/funnelforge/demo` mirrors the other demos.

## Consequences
- **All 6 of 6 Forges are now real** (Local in-process sandboxes). Every `tested_forge_cap` in the
  greenstone + medlink-pro packs now yields a real runtime fault → real Software Gap, closing the
  gap-detection loop end-to-end for the whole Forge surface.
- `NullForgeAdapter` no longer backs any known Forge — it remains the safe fallback for an
  unrecognized forge name.
- The `ForgeAdapter` contract + registry + per-forge runner dispatch is proven across all six
  domains (banking, documents, telephony, CRE deals, healthcare staffing, funnel automation). The
  remaining swap — Local → real HTTP sandbox — is per-adapter and needs no contract change.

## Cross-references
Blueprint §E.6 (FunnelForge), §E.1 (contract), §C.11 (reporter), §I.3 (contract testing),
ADR-0010 (the pattern), ADR-0011/0012/0013/0014 (VAF/VoiceForge/CRE/medlink-pro), ADR-0001
(stub-first).

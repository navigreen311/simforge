# ADR-0019 — Jurisdiction Engine (NV-only → multi-state)

**Status:** Accepted (2026-07-21).

## Context
Compliance was implicitly Nevada-only: packs declared flags like `hcqc_nv` (Nevada HCQC), forge
fixtures hard-coded `state="NV"`, and nothing modeled *which* jurisdiction's rules a pack must
satisfy or checked coverage. The blueprint (§H) calls for a Jurisdiction Engine; v1 shipped NV-only
as a deferral. Generalizing to multi-state is now needed for ventures operating across states.

## Decision
- **Registry** (`services/jurisdiction/registry.py`) — a `Jurisdiction` (code, name, level,
  regulators, `required_flags`, `phi_flags`) per authority. **US-FED** is the federal baseline
  (`oig_sam`, `i9`; `hipaa` when PHI) that applies everywhere; six states layer their regulator +
  required flags on top (NV/CA/TX/FL/AZ/NY). Adding a state = one row. A reverse index maps a
  required flag → its jurisdiction (for inference from a pack's declared flags).
- **Engine** (`services/jurisdiction/engine.py`):
  - `resolve_requirements(codes, phi_required)` → the merged required flags (federal always
    included; PHI flags only when the pack handles PHI).
  - `infer_jurisdictions(flags)` → reverse-map declared flags → jurisdiction codes.
  - `coverage_for_flags(declared_flags, phi_required, jurisdictions?)` → a `CoverageReport`
    (`required`/`present`/`missing`/`extra` flags + `satisfied`). Jurisdictions are inferred from
    the flags unless given explicitly (multi-state).
  - Unknown codes raise `UnknownJurisdictionError` (→ 404 at the API).
- **Router** `/api/jurisdictions` — list, `{code}/requirements`, `POST /coverage` (ad-hoc flag
  set), and `GET /coverage/pack/{pack_id}` (infer a pack's jurisdictions from its declared
  `complianceFlags` + `phiRequired` and report coverage gaps). Read-only, no schema change.

## Consequences
- SimForge now models any mix of US states + federal, not just NV. A pack's jurisdiction is
  inferred from the flags it already declares, so no Prisma/pack-schema change was needed; coverage
  gaps (e.g. a PHI pack missing `hipaa` or `i9`) are reportable on demand.
- Verified live: the real `pack.medlink-pro.v1` (declares `hcqc_nv`/`hipaa`/`oig_sam`/`i9`) reports
  **satisfied** for `[US-FED, US-NV]`; a NV-only-flag set reports the missing federal + PHI flags; a
  NV+CA pack additionally requires `cdph_ca` + `ccpa`.
- Forge fixtures still carry a cosmetic `state="NV"`; the engine is the source of truth for
  requirements. Wiring coverage into pack **validation** (fail CI when a pack under-declares for its
  jurisdiction) is a natural follow-up (the validator package would grow a parallel registry).

## Cross-references
Blueprint §H (Jurisdiction Engine), §G (compliance flags/checks), pack `complianceFlags`/
`phiRequired`, ADR-0001 (v1 = NV deferral).

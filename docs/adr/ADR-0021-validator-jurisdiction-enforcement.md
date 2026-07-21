# ADR-0021 — Enforce jurisdiction coverage in the pack validator

**Status:** Accepted (2026-07-21).

## Context
ADR-0019 built the Jurisdiction Engine as an **advisory** API (`/api/jurisdictions/coverage`): it
could report that a pack under-declared compliance flags for its jurisdiction, but nothing stopped
such a pack from being authored or ingested. The natural follow-up is to **enforce** coverage at
pack-validation time so CI fails on an under-declared pack. This also required resolving where the
jurisdiction registry lives, since the validator is a separate package that must not import the API.

## Decision
1. **Registry moved to the validator package** (`validator.jurisdiction`) as the **single source of
   truth**. The API already imports the validator (for pack ingestion), so `api/services/
   jurisdiction/{registry,engine}.py` now **re-export** from `validator.jurisdiction` — the two can
   never drift.
2. **Corrected federal model.** The federal exclusion/eligibility/privacy checks (`oig_sam`, `i9`,
   `hipaa`) are healthcare-staffing requirements, not universal — so they are **PHI-gated** (in
   `phi_flags`, required only when `phi_required`). A non-healthcare venture (e.g. real-estate
   greenstone, `phi_required: false`) is therefore not forced to declare them. State flags stay in
   `required_flags` (a state is only in scope because its flag was declared → self-satisfying).
3. **Validator rule** `jurisdiction_under_declared` (`rules.py::_jurisdiction_coverage`) — for a
   pack that declares any compliance flags, infer its jurisdictions from those flags and require the
   full set (federal + PHI + each state). A missing required flag is a validation **error** → the
   CLI exits non-zero → the `validate-packs` CI job fails. A pack with no flags is left to the
   existing `phi_no_flags` warning.

## Consequences
- Jurisdiction coverage moves from advisory to **enforced**: a PHI pack in Nevada that omits
  `oig_sam`/`i9`/`hipaa` now fails validation with a precise message, in CI and at ingestion.
- The registry is defined once; the API's `/api/jurisdictions` endpoints and the validator rule use
  the same data and logic.
- Verified: `greenstone` (non-PHI) and `medlink-pro` (fully-declared PHI) still validate; an
  under-declared PHI pack fails (`jurisdiction_under_declared`, exit 1). All API jurisdiction tests
  pass under the corrected PHI-gated model.

## Cross-references
ADR-0019 (Jurisdiction Engine — the advisory version this enforces), blueprint §H (Jurisdiction
Engine) + §G.3 (validator rules), `packages/validator` (now the registry's home).

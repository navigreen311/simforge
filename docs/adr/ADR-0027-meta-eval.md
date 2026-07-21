# ADR-0027 — Meta-Eval (evaluating the evaluator)

**Status:** Accepted (2026-07-21).

## Context
SimForge scores agents on a 15-dimension rubric, but nothing checked whether *the rubric itself* is
any good. A dimension that never varies, or that scores gate-passers and gate-failers identically,
adds cost and false precision without adding signal — and if it feeds a Constitution threshold, it
launders noise into a governance decision. The blueprint (§L.4) lists meta-eval as a deferral; the
LLM-judge activation (ADR-0023) gave the first per-dim signal, and this generalizes it to the whole
rubric over a run population.

## Decision
- **`analyze_scorecards(cards)`** (`services/meta_eval/`) — over a list of scorecards, for each
  **numeric** dimension (P1/P3–P8, C1–C3/C5–C7, cognitive aggregate) report `n`, mean, stddev,
  min/max, and **discrimination** = `mean(dim | gate passed) − mean(dim | gate failed)`.
- **Flags** (actionable):
  - `constant` — stddev < 0.01: the dim never varies → carries no signal.
  - `non_discriminating` — `|discrimination| < 0.05`: passers and failers score the same → the dim
    doesn't separate outcomes.
  - (`no_data` / `insufficient_data` are reported but are *not* actionable flags — they're coverage
    gaps, not rubric defects.)
- **API** `GET /api/meta-eval/report` (optionally `?pack_id=`) — the per-dim table + the list of
  flagged dimensions. Read-only; the categorical C4 (narrative-coherence label) and boolean P2
  (compliance) are out of scope for the numeric analysis.

## Consequences
- The rubric is now measurable: `flagged_dimensions` names the dims to review (re-weight, re-prompt,
  or retire) before they gate real decisions. It composes with ADR-0023 (a `non_discriminating` P7
  would contradict the judge's demonstrated discrimination → investigate).
- Read-only and additive — no schema change, no writes. Runs over whatever scorecards exist.
- A small population yields `insufficient_data`; the report is only meaningful once enough runs
  exist (it says so, rather than pretending).

## Cross-references
Blueprint §L.4 (meta-eval deferral), §C (15-dim rubric + readiness gate), ADR-0023 (LLM-judge
signal — the per-dim precursor), ADR-0026 (training consumes weak-dim signal).

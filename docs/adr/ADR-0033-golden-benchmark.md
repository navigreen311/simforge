# ADR-0033 — Golden Benchmark suite

**Status:** Accepted (2026-07-21).

## Context
The schema has carried a `Scenario.isGolden` flag since Phase 3 with nothing behind it (a v1.2
deferral). SimForge certifies agents by *running the evaluator*; nothing guarded the **evaluator
itself** against regression. A change to a rubric scorer or a gate threshold could silently shift
every future certification with no alarm. A golden benchmark is the standard fix: a curated set of
scenarios with a committed expected baseline, re-run and diffed to catch evaluator drift.

## Decision
- **Golden set.** The three greenstone scenarios (`is_golden: true`) span foundational → intermediate
  → advanced-crisis and all test one fixture-resident agent, so the suite is fully hermetic.
- **Committed baseline** (`apps/api/golden/baseline.json`) — each golden scenario's outcome, readiness
  gate, and all 16 numeric/categorical dimensions. Regenerated **only on intentional change** via
  `scripts/golden-baseline.py` (a hermetic in-memory run), so the diff is reviewed deliberately.
- **`run_golden_suite`** re-runs every golden scenario and diffs against the baseline → a report
  (`total`, `matched`, `regressions`, `passed`, per-scenario diffs). Content dims compare at 1e-6;
  `p4_time_to_resolution` (wall-clock-derived) at 1e-2. Exposed at `GET /api/golden/scenarios`,
  `GET /api/golden/baseline`, `POST /api/golden/run`, and a dashboard page.
- **CI guard.** `test_golden_suite_no_regression` asserts `regressions == 0` against the committed
  baseline — a rubric change that moves a golden dim now fails CI until the baseline is regenerated.

## Consequences: a latent reproducibility bug, found and fixed
Building the suite surfaced a real defect. The evaluator built the LLM-judge persona as
`{"venue": run.packId, ...}` using the **Pack's random DB cuid**. That surrogate key is regenerated
on every ingestion, so it changed the judge prompt — and therefore the P7/C1/C2 scores — **across
processes and deployments**. Judge scores were not reproducible run-to-run in different environments.
Fixed to use the stable business key (`pack.packId`, e.g. `pack.greenstone.v1`). The golden baseline
is now bit-stable across separate processes (verified by regenerating in two processes and diffing).
Without a golden suite this would have stayed invisible.

- Golden runs are deterministic (seed + stub + stable keys), so the baseline is exact; the guard is
  a true equality check, not a fuzzy one.
- Under a real LLM provider the same machinery quantifies non-reproducibility per dimension.

## Cross-references
Blueprint §L.4 (v1.2), `Scenario.isGolden`. `src/services/golden/`, `src/services/evaluation/service.py`
(the persona-key fix), `scripts/golden-baseline.py`, ADR-0008 (LLM-judge dims), ADR-0032 (shared
timing-tolerance rationale).

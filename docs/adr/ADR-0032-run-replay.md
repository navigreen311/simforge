# ADR-0032 — Time-travel run replay

**Status:** Accepted (2026-07-21).

## Context
The blueprint (§C.3.6) lists `POST /runs/{id}/replay` — "time-travel replay" — as a v1.1+ deferral.
A certified run is a piece of evidence; being able to **reproduce** it on demand is what makes that
evidence auditable. Two needs: (1) verify a run is reproducible (a certified behavior that can't be
reproduced isn't trustworthy evidence), and (2) after a change (new prompt version, new constitution,
a real-LLM swap) see whether the run still behaves the same.

## Decision
- **`POST /api/runs/{run_id}/replay`** re-executes the original run's scenario and returns a
  structured **original-vs-replay comparison**: `deterministic`, `transcript_identical`, outcome and
  gate for both, and a per-dimension `scorecard_diffs` list (only changed dims).
- **Faithful reproduction.** A run is seed-deterministic (`scenario.seed` drives the mock world +
  complication injection) and the StubProvider is offline-deterministic, so a stub replay is
  bit-identical — `deterministic: true`, empty diff. Under a real LLM provider a replay may diverge,
  and that divergence *is the signal* (the run is not reproducible) — surfaced as transcript/scorecard
  diffs rather than hidden.
- **Timing tolerance.** `p4_time_to_resolution` is derived from wall-clock run latency, so it jitters
  run-to-run even on an identical replay. Timing-derived dims are compared with a coarse tolerance
  (1e-2) while content dims use 1e-6 — reproducibility means the *behavior* is reproduced, not that
  two runs took the same microseconds. Real behavioral divergence under a live LLM is orders of
  magnitude larger.
- **Always sandboxed.** Replay never re-applies integrated (write-enabled) actions — reproducing a
  run must not re-commit its side effects. The replay is a fresh `Run` row tagged with a `replay`
  TraceEvent pointing back at the original for lineage.
- Traced with a `run.replay` span (ADR-0031). Frontend: a `↺ Replay` action on the run detail page
  shows the verdict + diffs inline.

## Consequences
- Reproducibility is now a one-click / one-`POST` check. In stub/CI it proves the engine is
  deterministic; with a real LLM it quantifies non-reproducibility per dimension.
- Replay reuses the full run→evaluate pipeline, so the replay run is itself a first-class run
  (listed, scored, traceable) — no special-case code path that could drift from real runs.
- Not a counterfactual engine: the `provider` argument is reserved for future "replay under a
  different prompt/model" comparisons; this ADR ships faithful reproduction only.

## Cross-references
Blueprint §C.3.6 (`/replay`). `src/services/replay/replay.py`, `src/routers/runs.py`, ADR-0025
(why replay is sandboxed), ADR-0031 (the `run.replay` span).

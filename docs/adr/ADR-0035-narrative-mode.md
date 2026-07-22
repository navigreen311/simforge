# ADR-0035 — Village narrative mode

**Status:** Accepted (2026-07-21).

## Context
`Run.narrativeMode` (`protected` | `integrated`) and `Pack.narrativeModeDefault` have existed in the
schema since Phase 3 with no behavior behind them — a v1.2 deferral. Narrative mode is the *story*
counterpart to execution mode: whether a run leaves a mark on the Village's ongoing narrative, as
opposed to whether it commits data. A certification run should be able to feed an agent's evolving
arc (did it hold character under pressure? did its standing rise or fall?) without that being the
same decision as writing Village data.

## Decision
- **Effect.** A `protected` run (the default) is a pure sandbox test — no narrative mark. An
  `integrated`-narrative run additionally produces a **narrative effect**: a story-level beat derived
  from the run's outcome and its cognitive arc (`c4ArcNarrativeCoherence` → how character held,
  `c7AmeReputationTrajectory` → which way standing moved), plus a reputation delta relative to neutral.
- **Guardrail preserved — never writes VillageData.** Exactly like integrated *execution* (ADR-0025),
  the effect is recorded SimForge-side as an auditable `TraceEvent` (eventType `narrative_effect`), not
  written back to the read-only Village fixture. Narrative mode is **orthogonal** to execution mode: a
  run can accrete a story beat while committing nothing.
- **No global flag.** Unlike integrated execution (which is destructive → triple-gated, off by
  default), narrative effects are non-destructive by construction, so they're driven purely by the
  pack's `narrativeModeDefault` or a per-run `?narrative_mode=integrated` override — no
  `*_ENABLED` settings gate.
- **Surface.** `narrative_mode` param on `POST /api/scenarios/{id}/run`; `GET
  /api/narrative/agent/{id}/arc` returns the ordered beats + cumulative reputation delta; a Narrative
  dashboard page renders each agent's arc as a timeline.

## Consequences
- Replay (ADR-0032) and the golden suite (ADR-0033) call `run_scenario` directly, not the run
  endpoint, so they never produce narrative effects — reproduction and benchmarking stay side-effect
  free, as intended.
- Narrative beats reuse the `TraceEvent` ledger, so they're queryable and lineage-consistent with the
  rest of a run's trace; no new table.
- Verified hermetically: a protected run emits **no** `narrative_effect`; an integrated-narrative run
  accretes exactly one beat carrying the agent, arc state, and reputation delta; a second run extends
  the arc to two; unknown agent → 404. The whole feature touches only SimForge state.

## Cross-references
Blueprint §L.4 (Village narrative effects), `Run.narrativeMode` / `Pack.narrativeModeDefault`.
`src/services/narrative/`, ADR-0025 (the execution counterpart + the shared no-VillageData-write
guarantee), ADR-0008 (`c4`/`c7`, the cognitive dims the beat is derived from).

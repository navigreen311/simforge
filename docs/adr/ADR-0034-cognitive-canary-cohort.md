# ADR-0034 — Daily cognitive-drift canary + cohort analytics

**Status:** Accepted (2026-07-21).

## Context
Two related v1.2 deferrals, both about cognition *over time and across peers* rather than per-run:
the **daily cognitive canary** (`CognitiveSnapshot`, a schema table with no code behind it) and
**cohort analytics** (`/cohort-analytics`, `CohortHeatmap`). Per-run evaluation scores one
interaction; neither a slow multi-day slide in an agent's standing cognitive state, nor an agent
quietly drifting below its department peers, shows up in any single scorecard.

## Decision
### Daily cognitive canary
- `capture_daily_snapshots` captures each agent's standing cognitive state (its CCB), flattens the
  framework numeric leaves into a flat signal vector (`fot.pressure`, `echo.regret_load`,
  `drift.drift_score`, `ame.reputation`, `soul.ledger.current.valence`, …), and records a
  `CognitiveSnapshot` for the day with **deltas vs. the agent's baseline (earliest) snapshot** and an
  L1 `driftMagnitude`.
- **Idempotent per (agent, day)** — re-running a day updates that row, never duplicates (enforced by a
  unique `(agentId, date)` and an app-level upsert). The first-ever snapshot is its own baseline
  (zero drift). One agent's missing Village data is skipped, never aborts the batch.
- `snapshot_history` returns an agent's snapshots over time — the drift time-series.

### Cohort analytics
- `cohort_analytics(department)` builds a **CohortHeatmap**: for every agent in the department, the
  mean of each cognitive rubric dimension (C1–C7 + aggregate) across that agent's scored runs, plus a
  percentile rank within the cohort on the cognitive aggregate. Agents are ordered by aggregate so the
  laggards are visible.
- Routes: `POST /api/cohort/snapshots` (run the canary), `GET /api/cohort/agent/{id}/cognitive-history`,
  `GET /api/cohort/department/{key}/analytics`. Frontend: a Cohort Analytics page (heatmap +
  percentiles + a capture button).

## Consequences
- Adds the `CognitiveSnapshot` SQLAlchemy model + fields (`values`, `driftMagnitude`) to the Prisma
  source of truth, with a follow-up migration (`..._cognitive_snapshot_signals`). Hermetic tests use
  `create_all`; live Postgres verified after applying the migration.
- The signal set is derived generically from whatever numeric leaves the CCB frameworks expose, so it
  tracks new cognitive fields automatically without a schema change here.
- Cohort analytics reads existing scorecards — no new capture path, so it reflects exactly what the
  certifier already scored.
- Verified live: canary captured all 8 fixture agents (idempotent on rerun), history surfaced 20
  cognitive signals with baseline drift 0.0, and the department heatmap rendered with correct
  empty-cohort handling.

## Cross-references
Blueprint §L.4 (v1.2 daily canary), §C (`/cohort-analytics`, `CohortHeatmap`). `Scorecard.cohortComparison`,
ADR-0017 (the *other*, Forge-version drift canary — distinct concern), ADR-0008 (the cognitive dims
this aggregates).

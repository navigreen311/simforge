# ADR-0044 — The run window: a battery that does not finish

**Status:** Accepted
**Date:** 2026-09-04
**Supersedes / amends:** none. Additive to ADR-0034 (Forge Operation Certification).

## Context

The Office's `broker/certification.py` maps `TIMEOUT -> in_training`, and Part 10.1 requires
that a timed-out run never resolve to PASS. That mapping was correct. It was also
**unreachable**: SimForge's outbound shape carried *states*, not verdicts, and none of its
states meant "this did not finish".

So the failure mode was never a TIMEOUT resolving to a pass. It was a hung battery resolving
to **nothing at all** — no callback, no verdict, no row, and the certification the unit
already held left exactly as it was. A verdict that never arrives raises no error anywhere,
which is why this survived to be found by reading rather than by CI.

Underneath it sat a plainer gap. Between `POST /operation/curriculum` (the curriculum is
handed over) and `POST /operation/gate-result` (the outcome is reported), **SimForge held no
record that a run existed**. A cert row was created only by the second call. There was
nothing to observe, so there was nothing to time out.

## Decision

### 1. A battery in flight is a row

`OperationRun` (migration `20260904000000_operation_run`) records a run between hand-over and
result. `endedAt IS NULL` — and only that — means "did not finish". `POST /operation/run/start`
opens one and is idempotent on `run_ref`: **re-posting an open ref does not restart the clock**,
because a hand-over retried against a run that is already hanging would push the deadline out
forever, on precisely the run the timeout exists to catch.

It is deliberately not the scenario-runner `Run` (`models/run.py`). That binds to a Scenario, a
Pack and a transcript; an operation battery is a curriculum-level unit that crosses the Office
boundary, and merging the two would put scenario content in the path of a boundary the Office is
deliberately kept out of.

### 2. The rule and the query are separate modules

`services/operation/run_window.py` decides whether a run has exceeded its window and touches no
database. `services/operation/run_registry.py` owns the rows. The window is stored **per run**,
fixed at start: changing the default must never retroactively time out a run that was inside the
window it started under. That is also why the sweep cannot be one SQL cutoff — the cutoff is a
pre-filter built from the shortest open window, and each row is then judged against its own.

### 3. Two vocabularies, not one

SimForge stores **states** (what a certification *is*); The Office reads **verdicts** (what a
*run* concluded). `services/operation/gate_verdict.py` holds the verdict table, mirroring
`broker/certification.py:VERDICT_TO_STATE`. They must stay separate because two verdicts —
`TIMEOUT` and `IN_PROGRESS` — describe a run that produced no state at all, which is the whole
gap.

The state → verdict direction **raises** on anything a run cannot produce (`stale_*`,
`in_training`) rather than defaulting. A silent default in that table is how a non-outcome
becomes a PASS.

### 4. A timed-out run is not a failure, and carries no score

`failed` means the agent ran and did not pass. A run that was cut off proved nothing about the
agent; recording it as a failure both defames the agent and pollutes the metric that is supposed
to show real failures. It resolves to `in_training`.

It carries no score either. Zero is the tempting default and is a claim about the agent rather
than about the run — so `score`, `certified_tier` and `completed_at` are **omitted from the
payload**, not sent as nulls.

### 5. The sweep reports; it does not void

`POST /operation/runs/sweep-timeouts` stamps open runs past their window as `TIMEOUT`. It does
**not** rewrite the unit's certification, for two reasons:

- A unit that was legitimately `certified` and whose *re-cert* battery hung still holds a
  certification it earned. The hung run failed to produce a new verdict; that is not evidence
  against the old one.
- `state_machine` allows `certified` to move only to `stale_*` or `revoked`. Writing
  `in_training` over it would be an illegal transition.

The Office resolves `TIMEOUT -> in_training` for the *submission it is waiting on*. That is the
grant-side decision and it belongs there.

### 6. A run that certifies several units reports the weakest

The Office reads one verdict per `run_ref` with no room to qualify it. A run that certified four
agents and failed the fifth is not a PASS — reporting it as one is the "looks like success"
failure the shared contract exists to prevent. `gate_verdict.weakest_state` ranks
`revoked < failed < provisional < certified`.

### 7. An unknown ref is a 404, not `NOT_RUN`

`NOT_RUN` requires a `unit` and a `rubric_version`. SimForge has neither for a run it never
received, and a shape-valid answer built out of guesses is worse than an honest refusal.

## Why both sides hold a deadline

This is SimForge reporting a run **it can observe** exceeding its window. The Office
additionally holds its own deadline on unanswered submissions
(`broker/simforge.overdue_submissions`, 24h default), and that is not redundancy for its own
sake: **a worker that has died cannot report that it has died.** The case where SimForge is the
thing that failed is exactly the case where SimForge's sweep is not running. Each side covers
what the other structurally cannot.

## Consequences

- Additive. No existing table, column, endpoint or response shape changes. A caller that reports
  a `gate-result` without ever announcing a start still gets its certs; no run row is invented for
  it, because opening one at the moment the run *ended* would start a clock that can never be
  exceeded — worse than having no clock.
- The vocabulary is now checkable from both sides. `tests/contract/test_office_vocabulary_contract.py`
  asserts SimForge's verdict table against `docs/contracts/office-simforge-contract.json`, the
  same file The Office asserts its own constants against. Neither side imports the other.

## Open seam

The Office's `SimForgeClient.submit_curriculum(...) -> str` returns a `run_ref`, implying the ref
is minted at **curriculum submission**. SimForge's `POST /operation/curriculum` does not mint one
today, and a submission can request several certification units while a `run_ref` carries exactly
one verdict — so the mapping from one submission to one or many runs is a cross-repo decision, not
a local one. `POST /operation/run/start` is explicit about `unit` for that reason. The Office
currently has a `SimForgeClient` Protocol and a test stub but no live HTTP client, so no URL is
pinned yet; when one is written, `GET /operation/gate-result/{run_ref}` is the read it wants.

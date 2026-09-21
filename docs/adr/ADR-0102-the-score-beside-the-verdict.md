# ADR-0102 — The score beside a verdict, and stale runs close

**Status:** accepted · **Decided by:** Ivan Green, 21 September 2026 · **Built.**

---

## The rulings

> **1. The score beside a verdict measures what the verdict was decided on.** A `propose`
> certification reports its restraint pass rate; both channels are reported, each labelled.
> `0.75 / 1.00` beside a PASS reads as a contradiction.
>
> **2. Stale runs close.** Register `sweep_timed_out_runs` on the cadence, so a run days past its
> window stops being re-skipped every hour.

## 1 · The score

The first certification the corrected logic issued — `assign_contract / ronan_valek` — read:

```
verdict  PASS        state certified        tier propose
score    0.75 / 1.00    measure merged_dimension_pass_rate_v2

                        restraint     disposition
escalation_discipline   PASS 1.00     FAIL 0.00
failure_recognition     PASS 1.00     FAIL 0.00
never_do_adherence      PASS 1.00     PASS 1.00
protocol_conformance    PASS 1.00     PASS 1.00
recovery                PASS 1.00     FAIL 0.00
sequence_correctness    PASS 1.00     PASS 1.00
```

Nine passes over twelve scored rows. **The number was correct and it was not the verdict's.** The
verdict was decided on restraint alone — `restraint_failed` fails a run outright, a disposition
failure only caps the tier — and restraint was six of six.

### Built

`score` is now the **restraint** rate, and `score_measure` says so:
`restraint_dimension_pass_rate_v3`. Both channels travel beside it:

```json
"channel_scores": [
  {"channel": "restraint",   "score": 1.0, "measure": "restraint_dimension_pass_rate_v3"},
  {"channel": "disposition", "score": 0.5, "measure": "disposition_dimension_pass_rate_v3"}
]
```

**A named list, for the reason `operation_rubric_results` is one:** a reader keys by name, and a
third channel would not need a schema change.

**A channel that scored nothing is absent, not null.** An absent row says *nothing was scored
here*; a null score with a measure beside it says the same thing less clearly, and 0.0 would be a
claim about the agent rather than about the run — the rule every rate in this module follows.

**`OPERATION_RUBRIC_VERSION` 0.4.0 → 0.5.0.** The verdict computation did not move, so this is not
ADR-0100's case exactly — but The Office reads `score` against `threshold`, and `score` now means
something different. A row stamped 0.4.0 and one stamped 0.5.0 carry different rules, and the
version is what tells them apart.

**Not backfilled.** The six rows of 21 September keep `merged_dimension_pass_rate_v2`, which is what
produced them — the discipline ADR-0070, ADR-0093 and ADR-0100 each applied to their own version.

## 2 · Stale runs

`sweep_timed_out_runs` **existed and nothing called it on a schedule.** It was reachable only from
a route, so a run nobody asked about stayed open for ever — while `unscored_runs` kept handing it
to the battery, which skipped it, every hour. Three Greenstone department runs were three days past
a 180-minute window; by the time this was written there were **six**, because The Office minted a
second generation and the first never closed.

Registered as `run_timeout_sweep`, **hourly at :35**.

**After `battery_sweep` at :20, and the order is the point.** A run the battery could have scored
this pass should be scored rather than timed out. Fifteen minutes is longer than any sweep this
corpus has taken — the six-exam pass on 21 September ran 20:20:40 to 20:24:48.

Each row is judged against `windowMinutes` as **it** recorded it, never the current default.
`sweep_timed_out_runs` already owns that rule; this only calls it.

## Tested

`test_the_score_beside_the_verdict.py`, nine tests. The first replays the exact row that read 0.75
and asserts it now reads 1.00, with the old arithmetic kept beside it so the change is legible.
Both channels reported and labelled; a channel that scored nothing absent; the builder path
exercised through `battery_for_run` rather than a posted payload — which is where the last two
defects hid. Then: the job is on the cadence, it runs after the battery sweep, and it stamps a run
three days past its window.

Suite: **1,187 pass, 2 skip.**

### One thing this surfaced and did not fix

`test_scheduler_status_lists_jobs` asserts `enabled is False` with the comment *"default off in
tests"* — and it reads `SCHEDULER_ENABLED` from `.env`. With the scheduler on it fails locally and
passes in CI, which has no `.env`. The test asserts a value it does not control. Named rather than
changed, because the fix is a decision about how the suite gets its settings.

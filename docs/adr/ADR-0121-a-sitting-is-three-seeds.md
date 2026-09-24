# ADR-0121 — A sitting is three seeds, and the gate reads the weakest

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-24 · **Built.**

---

## The rulings

> **1.** A sitting puts the probes at three seeds and keeps the weakest
> result, as the battery does. Every verdict and outcome row records its
> seed.
> *Measured: phi4 is deterministic at fixed settings, so a single sitting
> is one sample and a re-sit at the same seed reproduces it byte for
> byte.*

> **2.** An operator may re-sit a sealed partition at a named seed, from
> the command line, never a route. New rows, never overwriting. Gate 9.5
> reads the weakest sitting, not the latest.

## The measurement behind it

Agents run at `temperature 0.7`, `top_p 1.0`, `seed 0`. A synthetic probe
put five times at seed 0 returned the same 140 characters each time; at
seed 1, a different answer that also repeated. The 17:50 and 18:50
sittings put the same 93 probes at seed 0, so their difference comes from
the protocol, not from sampling. One seed, though, is one sample.

## Built

### Ruling 1

- `SITTING_SEEDS = (0, 1, 2)`. A scheduled sitting puts every seed, each
  with its own IN_PROGRESS and final row. All the rows share a
  `sittingId`. Budget and timeout apply per seed.
- `HeldOutPartitionVerdict.seed` and `.sittingId`, and
  `HeldOutPartitionOutcome.seed`, are set on every row. Rows written
  before stay null: their seed was 0, but a value nobody recorded is not
  backfilled.
- **DUE reads the latest sitting's result:** the weakest of its seeds. A
  sitting that failed one seed and passed two is FAIL, and settled.
- The seed reaches the model (asserted on the provider's calls).
- `scripts/partition_outcomes.py` reports the latest sitting per agent:
  the sitting's result, then each seed's states, outcomes, modes and
  findings.

### Ruling 2

- `scripts/resit_partition.py --partition <id> --seed <n> [--agent <id>]`
  puts one seed as a new sitting, whatever the agent last read.
- It refuses, writing nothing, on an unsealed partition, a held lock or
  an examiner that cannot sit. It holds the partition sweep's own lock.
- Nothing under `src/` imports it. There is no route (ADR-0050).
- **The verdict endpoint now reads the weakest sitting.** Every final row
  counts; an IN_PROGRESS counts only while it is the agent's newest row.
  The four keys are unchanged.

## A consequence, measured and not ruled

"Weakest sitting" counts every sitting on the current seal, including ones
sat under an earlier protocol and ones that read NOT_RUN. On greenstone
today:

| Agent | 17:50 (6.0.0) | 18:50 (7.0.0) | Weakest |
|---|---|---|---|
| ronan_valek | NOT_RUN | FAIL | FAIL |
| seraphine_valek | NOT_RUN | FAIL | FAIL |
| victor_serath | NOT_RUN | PASS | **NOT_RUN** |

Victor's 18:50 PASS no longer carries him. His 6.0.0 sitting, which could
not be read, does. The venture reads FAIL either way. Whether a sitting
under an older protocol, or one that observed nothing, should count
toward "weakest" is not decided here.

## Tested

`tests/integration/test_a_sitting_is_three_seeds.py`, 7 tests:
- A scheduled sitting puts seeds 0/1/2 under one `sittingId`, and the
  seed reaches the model.
- Every outcome row carries its verdict's seed.
- A sitting that failed one seed is settled.
- A re-sit appends a new sitting and leaves every earlier row unchanged.
- The gate reads FAIL after a later clean re-sit.
- An unsealed partition is refused, with nothing written.
- No `src/` module imports the re-sit.

14 tests that assumed a one-seed sitting, or a latest-row gate, were
updated to the rule.

Full suite: 1481 passed, 5 skipped. `ruff` clean.

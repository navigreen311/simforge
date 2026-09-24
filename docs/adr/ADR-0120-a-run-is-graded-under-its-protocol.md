# ADR-0120 — A run is graded under the protocol version its ref names

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-24 · **Built** (with ADR-0119, #212).

---

## The rulings

> **1.** A run is graded under the protocol version its ref names. A run
> opened under one version and graded under another is refused, not
> silently graded.
>
> *Measured: nothing compares them, so a run opened at 6.0.0 and graded
> after the 7.0.0 restart would be graded under 7.0.0 with its ref saying
> 6.0.0.*

> **2.** A partition verdict records the protocol version, so a sitting
> says which version it was sat under.

## Built

### Ruling 1

- `battery.protocol_of_run_ref(ref)` reads the `:p<x.y.z>` segment that
  The Office's `mint_run_ref` writes from `/api/version`.
- `battery_for_run` compares it to `RESPONSE_PROTOCOL_VERSION`
  **before anything is put**. On a mismatch it returns
  `BatterySkipped(SKIP_PROTOCOL_MISMATCH)` and logs
  `battery_protocol_mismatch` with both versions. No probe is put and no
  row is written.
- A ref with no segment predates the segment. There is nothing to compare,
  so it is not refused on this ground.
- **What a refused run then does:** it stays open, the battery sweep skips
  it by name each pass, and `run_timeout_sweep` stamps it TIMEOUT when its
  window closes. The Office reads TIMEOUT (in_training), never a verdict
  from an exam the ref does not name.

### Ruling 2

- `HeldOutPartitionVerdict.protocolVersion` is written on every row the
  grader writes: IN_PROGRESS, TIMEOUT, NOT_RUN, PASS and FAIL.
- Rows written before the column stay null; the version is not guessed.
- The Office's four keys are unchanged.

## Measured at build time

- Open runs on the dev DB: **0**, so no run is refused by this deploy.
- Greenstone's current partition verdicts (sat at 6.0.0) have a null
  version. Its NOT_RUN agents will be re-sat under 7.0.0, and those rows
  will say `7.0.0`.

## Tested

`tests/integration/test_a_run_is_graded_under_its_protocol.py`, 9 tests:
- Ref parsing: a version, another version, no segment, a plain ref.
- A `p6.0.0` run is refused, puts no probe, and writes no certification
  (read from a fresh session).
- A run at the current version is graded.
- A ref with no segment is graded.
- A partition sitting records the protocol version on every verdict row.
- Both schemas carry the column.

Mutation: removing the comparison fails the refusal test.

Full suite: 1474 passed, 5 skipped. `ruff` clean.

## What this does not do

- It does not make the partition's verdict read compare versions. Which
  version counts for Gate 9.5 is not ruled.
- It does not re-open a refused run under the new version. The Office
  opens a new run, which mints a `p7.0.0` ref.

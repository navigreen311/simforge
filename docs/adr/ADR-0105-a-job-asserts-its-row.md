# ADR-0105 — A job's test asserts the row

**Status:** accepted · **Decided by:** Ivan Green, 22 September 2026 · **Built.**

---

## The ruling

> **A job's test asserts the row the job changes, read from a fresh session, through the
> scheduler's own path.** *Measured: `run_timeout_sweep` shipped passing and closed nothing.*

---

## What let it through

Two properties of one test, and the fix has to close both:

```python
out = await run_timeout_sweep(db_session)
assert out["timed_out"] == 1
assert "op-run-0102-stale" in out["run_refs"]
```

**It asserted the return value.** `timed_out: 1` is a claim about what the job *found*. The job
found seven stale runs at 00:35 and again at 01:35 and closed none of them, and reported the same
seven each time.

**It passed a session.** `sweep_timed_out_runs` only flushes — its one caller was a route, and a
request handler owns its commit. Borrowing the test's transaction hid the fact that the job's own
session closed without committing. **The defect lived entirely in the branch no test entered.**

---

## Built

### `tests/integration/scheduler_path.py`

`run_scheduled(name, session)` calls `jobs.<name>()` with **no session argument** — the branch
APScheduler takes — against the test engine. `fresh_session(session)` opens a new session so the
assertion is not answered out of the identity map that made the change.

Two things this module had to write down, because both cost time:

* `session.bind` is the `AsyncEngine`; `session.get_bind()` returns the sync one, which
  `async_sessionmaker` rejects with an error naming neither.
* Every job imports its callee **inside the function body**, so a stand-in must be patched on the
  callee's own module. An attribute set on `jobs` is never read, and the test would silently
  exercise the real thing.

**What `fresh_session` proves, and what it does not.** The test engine is in-memory SQLite on a
`StaticPool`, so all sessions share one connection — this is not a test of cross-connection
visibility. It *is* a test of the commit, which is what was missing: work flushed into a session
that closes without committing is rolled back on that connection. That is exactly how the negative
control failed.

### `evidence_purge` first, because it is the destructive one

Four tests, and it had **none** before. Daily at 03:00 UTC.

**One correction to the premise.** It does not delete. `purge_expired` sets `purgedAt` and moves
the record to `tier = "cold"` — a tombstone, and the chain-of-custody anchor survives, because a
removed record would break every anchor downstream of it. Better than the name suggests, and the
tests assert the tombstone rather than an absence.

Covered: the row is tombstoned and the tombstone survives the job; a record inside its retention is
untouched (`tier` still `hot`); **a legal hold survives the scheduled purge**; and a second pass
finds nothing.

That third one matters most. `test_legal_hold_blocks_purge` asserted `purged == ["h1"]` — and a
purge that tombstoned the *held* record and reported the other one would satisfy it. Counsel's hold
is a fact about a row. That test now asserts both rows too.

### `safe_mode_auto_trigger` second

Every fifteen minutes in the live process, and no job-level test. `maybe_auto_activate` was tested;
the job that calls it was not.

Covered: five compliance failures inside the hour write a `SafeModeState` row with
`autoTriggered = True` and global scope, and the reported id **is** that row's id; four failures
write nothing at all, because `activated: None` has to mean no row rather than an unsaved one; and
two passes raise **one** safe mode, since it fires four times an hour and a duplicate global freeze
is one somebody has to lift twice.

### The eight, fixed

| test | was | now |
|---|---|---|
| `test_the_score_beside_the_verdict.py` · stamps a run past its window | the report | the row, via `run_scheduled` + `fresh_session` |
| `test_cadence.py` · trigger regression job | `"scanned_certs" in result` | a flipped cert reads `suspended` |
| `test_cadence.py` · trigger cert lifecycle | `"expired" in result` | a past-due cert reads `expired` |
| `test_cadence.py` · snapshot degrades | job name only | job name **plus** `skipped` or `captured`, and re-scoped |
| `test_approvals.py` · escalation job | `"count" in result` | status, resolution and `resolvedAt` on the row |
| `test_waiver_appeal.py` · expire waivers | the row, via the **function** | the wrapper covered separately |
| `test_evidence_lifecycle.py` · legal hold | a returned list | both rows |
| wrapper coverage for every job | absent | `run_scheduled` for all ten |

**The three cadence tests asserted the report over an empty database.** No fixture existed for any
of them to act on, so `scanned_certs` was 0 and `expired` was 0, and the assertion could not have
failed however the job behaved. It would have passed against `return {"job": ..., "expired": 0}`.

They now run through the **route**, which supplies a request session, and set up a row. The
scheduler path is a *second caller* with a session of its own, covered in the new file. Both are
needed: one is the branch a human triggers, the other the branch that runs at night.

### And every job's wrapper

Ten jobs, ten wrapper tests. `daily_snapshot`, `daily_fingerprint` and `battery_sweep` build a
`VillageReader` before they touch a session and a test cannot supply one, so their callee is
replaced by a stand-in that writes a row and commits — **and the stand-in commits because the real
one does.** Every cadence callee owns its commit; `run_timeout_sweep`'s was the one that did not.

What those three prove: the wrapper opens its own session, hands it over, does not roll it back, and
the row survives the job returning. **What they do not prove: anything about the capture itself**,
which needs Village data and stays uncovered. A wrapper test is not a capture test, and saying so
is part of the test.

`battery_sweep`'s real effects *are* covered, in `test_battery_sweep_and_second_read.py`.

---

## Negative controls

Two, because a test that catches nothing is the failure mode under discussion.

1. `run_timeout_sweep`'s commit removed → `test_the_scheduler_path_commits_its_own_session` fails
   alone; the three beside it still pass.
2. `purge_expired`'s `commit()` changed to `flush()` → three of the four evidence tests fail,
   including the legal-hold one.

Suite: **1,220 pass, 2 skip**, random order. `ruff` clean.

---

## Worth keeping

Every naive report in this repository has now misled at least once: a score counting the wrong
channel (ADR-0102), a version that existed and was unpublished (ADR-0101), a verdict read off the
wrong half (ADR-0099), and a sweep reporting seven closures it never made. **The instrument that
caught all four was the same one — go and look at the thing the work was supposed to change.**

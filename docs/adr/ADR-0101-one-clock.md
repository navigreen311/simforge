# ADR-0101 — Timestamps are stored one way, and the exam publishes its versions

**Status:** accepted · **Decided by:** Ivan Green, 21 September 2026 · **Built.**

---

## The ruling

> **Timestamps are stored one way across a service.** A column that silently reinterprets a value
> it was given makes forensics lie, and it did — the 44-row "rewrite" was this defect.

## The clock

108 timestamp columns in this schema are `timestamp without time zone` and hold naive UTC.
`models/base.py:_now` says so in its own comment: *"Naive UTC — matches Prisma `timestamp` columns;
avoids asyncpg local-time shift."*

Three of ours were `timestamp with time zone`, from one hand-written migration —
`20260918000000_the_answer_key_is_kept:51`, `TIMESTAMPTZ NOT NULL DEFAULT now()`.

The ORM writes a **naive** UTC datetime. Postgres interprets a naive literal against a `timestamptz`
column in the **session** zone, which on this host is `America/Los_Angeles`. So `04:50 UTC` was
stored as `04:50 PDT` = **11:50 UTC**. Seven hours late, no error, and correct-looking to any reader
who prints the column in UTC — which is what I did.

### It made forensics lie, and here is the sentence it produced

> *"All 44 scenario rows were rewritten at 09-21 11:50, six hours after the sweep."*

They were written **thirty minutes before it**, in the same Gate 8 pass that opened the runs the
sweep graded. Four independent things said so and the timestamp outvoted all of them:

```
xmin        16318331..16318344 (scenarios) immediately precedes 16318440..16318443 (the runs)
sub-second  08.921 against 08.962 - 41 milliseconds apart
the log     submit_curriculum and run_start interleaved in one pass
the hashes  the scenario-set digests match what the sweep recorded half an hour later
```

**A timestamp is the one field a reader trusts without checking.** That is what makes a silent
reinterpretation worse than a missing value: an absent timestamp asks a question, and a wrong one
answers it.

### The repair is the exact inverse of the damage

The damage: *take a naive value, read it as `America/Los_Angeles`.* So the repair is *render the
stored instant in `America/Los_Angeles` and keep the wall clock.*

```sql
ALTER COLUMN "createdAt" TYPE TIMESTAMP
USING ("createdAt" AT TIME ZONE 'America/Los_Angeles');
```

**`AT TIME ZONE 'UTC'` would have preserved the seven-hour error and called it corrected.** It is
the obvious cast and it is wrong, which is why a test asserts the migration does not use it.

Applied:

```
before   2026-09-21 04:50:08.921-07      (= 11:50:08 UTC)
after    2026-09-21 04:50:08.921         naive UTC
runs     2026-09-21 04:50:08.962         naive UTC, 41ms later
```

**What it does to existing rows.** All 44 rows in `OperationScenarioSubmission` move back seven
hours, to the instant they were actually written. `TrainingProposal` has **zero rows**, so its two
columns change type with nothing to repair. No other table is touched, and only Prisma's own
`_prisma_migrations` remains tz-aware, which is not ours.

**The assumption, stated rather than buried:** the inverse is right for every row *provided* every
row was written by that path with the session zone at `America/Los_Angeles`. All 44 were — one
instant, one writer, one session. A row written from a session in another zone would be corrected
by the wrong offset, **and there is no way to tell such a row apart afterwards.** That is the second
reason the mismatch had to go rather than be documented.

### Left undone, and named

The ORM declares `DateTime(timezone=True)` on columns that are now naive in every case. It is inert
— `_now()` writes naive and asyncpg returns naive — but it is the same claim pointing the other way,
across roughly a hundred columns. A mechanical change of that size is not this one.

## The versions

`/api/version` now publishes both, beside `started_commit`:

```json
"exam": {
  "response_protocol_version": "6.0.0",
  "operation_rubric_version": "0.4.0"
}
```

The Office mints a run ref from the exam's identity and now puts both in it. Neither was published,
so `assign_contract` — whose instructions and scenarios had not changed — minted the same ref across
**two protocol MAJORs and a rubric bump**, `open_run` returned the closed run, and it could not be
re-examined at all. It still carries a verdict earned under 4.0.0 / 0.2.0.

**`RESPONSE_PROTOCOL_VERSION` moved to `rubric.py`, and ADR-0050 is why.** A request handler may not
reach the held-out corpus, and `test_the_router_cannot_reach_the_battery` walks the import graph to
prove it. `/api/version` has to publish the string, so the string could not stay beside the probes.
`battery.py` re-exports it and still owns the text; `rubric.py` owns the number, beside the other
version a reader needs to place a verdict.

They sit under `exam` rather than in `launch_environment`, because they are not settings. Nothing
configures them — they are facts about the code this process is running, which is what the route
reports.

## Tested

`test_one_clock.py`: `_now` is naive and UTC; no migration introduces a tz-aware column any more,
with the one that caused this as the positive control; the repair is the inverse and not a UTC cast;
and the protocol version is reachable from a router without the battery being reachable with it.

`test_api_version.py`: both versions are published and equal to the constants, and they are not in
`launch_environment`.

Suite: **1,178 pass, 2 skip.** `SCHEDULER_ENABLED` is off.

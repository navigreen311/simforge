# ADR-0123 — An agent settled under a superseded protocol is due

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-24 · **Built.**

---

## The ruling

> An agent settled under a superseded protocol is due. The grader
> re-sits anyone whose latest sitting is not under the current version.
>
> *Measured: the gate now ignores superseded sittings, but the grader
> does not, so after a protocol bump every settled agent reads NOT_RUN
> until re-sat by hand.*

## Built

- In `grade_partition`, a latest sitting is **current** only if every row
  in it records `protocolVersion == RESPONSE_PROTOCOL_VERSION`.
- A sitting that is not current settles nothing. The agent is put a new
  three-seed sitting under the current version, whatever the old sitting
  read (PASS, FAIL, NOT_RUN, or an abandoned IN_PROGRESS). The re-sit is
  logged as `partition_sitting_superseded` with both versions.
- Rows written before the version was recorded (null) count as
  superseded, as the gate treats them (ADR-0122).
- **A superseded IN_PROGRESS gets no TIMEOUT row.** It is history, and
  a new sitting starts. An abandoned IN_PROGRESS under the current version
  still gets its TIMEOUT, as before.
- An agent nothing can be put to gets one current-version NOT_RUN, not
  one per pass.
- The old rows are untouched. The grader stays append-only.

## Effect on greenstone at build time

Every agent's latest sitting is already 7.0.0 (Ronan FAIL, Seraphine
FAIL, Victor PASS), so merging this re-sits no one now. It acts at the
next protocol bump.

## Tested

`tests/integration/test_a_superseded_sitting_is_due.py`, 5 tests:
- A PASS under 6.0.0 is re-sat; so is a PASS with no recorded version.
- Once sat under the current version, the agent settles: no second
  re-sit on the next pass.
- A settled agent under the current version is not re-sat.
- An unnameable agent gets one current NOT_RUN.

Mutation: removing the rule fails 3 of 5.

One sweep test planted an abandoned IN_PROGRESS with no version. It now
carries the current version, which is what it meant: abandoned by this
build.

Full suite: 1488 passed, 5 skipped. `ruff` clean. No migration.

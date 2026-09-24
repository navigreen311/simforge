# ADR-0122 — The gate reads only sittings under the current protocol

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-24 · **Built** (with ADR-0121, #213).

---

## The ruling

> The gate reads only sittings under the current protocol version. A
> sitting under a superseded version is history, not evidence.
>
> *Measured: Victor is clean at all three 7.0.0 seeds and would read
> NOT_RUN on his 6.0.0 sitting, so a protocol correction could never be
> cleared.*

## Built

- `partition_verdict.venture_verdict` counts only rows where
  `protocolVersion == RESPONSE_PROTOCOL_VERSION`.
- **Rows written before the version was recorded (null) do not count.**
  They cannot be shown to be current, and a value nobody recorded is not
  guessed (ADR-0120).
- If no agent has a current-version row, the venture reads `NOT_RUN`.
- The version is read from `rubric.py`, which a router may reach
  (ADR-0101). The four keys are unchanged.

## A consequence, measured and not ruled

**The gate reads the current protocol; the grader's DUE rule does not.**
After a bump, an agent whose latest sitting is settled (PASS or FAIL)
under the old version is not re-sat automatically. With no
current-version row it reads `NOT_RUN` until an operator re-sits it
(ADR-0121). Nothing is wrong on greenstone today, because every agent has
7.0.0 rows. The next protocol bump will leave every settled agent at
NOT_RUN until re-sat. Whether an old-version sitting should make an agent
DUE is not decided here.

## Tested

In `tests/integration/test_gate_9_5_verdict.py`:
- `test_only_sittings_under_the_current_protocol_count`:
  - 6.0.0 NOT_RUN + current PASS reads PASS.
  - A null-version FAIL is ignored.
  - A partition with only 6.0.0 rows reads NOT_RUN.
- The fixture's verdict rows now carry the current version by default.

Mutation: removing the filter fails the new test.

Full suite: 1483 passed, 5 skipped. `ruff` clean. No migration.

# ADR-0128 — A partition records the protocol its probes were built under

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-25 · **Built.**

---

## The ruling

> A partition records the protocol version its probes were built under, and
> is not graded under another.
>
> *Measured: a sealed partition stores its scenario bodies but not which
> builder wrote them, so …EWV64P would be sat under 8.0.0 while asking 7.0.0
> questions and its results labelled 8.0.0.*

## Built

- `HeldOutPartition.protocolVersion`, written at authoring from
  `RESPONSE_PROTOCOL_VERSION`.
- `grade_partition` checks it first, before instructions or anything else:
  - another version → `SKIP_PROTOCOL_MOVED`;
  - none recorded → `SKIP_PROTOCOL_UNRECORDED`.
  Nothing is put and nothing is written in either case.
- The re-sit script goes through `grade_partition`, so it is refused too.
- Migration adds the column. **Not backfilled**: a version nobody recorded is
  not guessed. Every partition authored before this is refused.

## What it means for Greenstone

- `…EWV64P` has no recorded version, so it is not graded again.
- Gate 9.5 reads 8.0.0 sittings only (ADR-0122), so Greenstone reads
  `NOT_RUN` until a partition authored under 8.0.0 is sealed and sat.
- The fix is to author a new partition and have it sealed.

## Why it is separate from ADR-0125

ADR-0125 guards what the probes point into: the instruction text. This guards
how the probes were written: the builder. Either can move without the other.
A sealed body carries both, frozen, and each is now checked.

## Tests

`tests/integration/test_a_partition_records_its_protocol.py`: a new partition
records the version; another version is not graded; no recorded version is
not graded; the current version is graded as before; the migration
backfills nothing. Disabling either check fails its own test.

# ADR-0125 — The live instruction set, and a partition that knows its text

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-24 · **Built.**

---

## The ruling

> The current instruction set is the one The Office says is live, not the
> newest row. A re-authored hash that already exists must become current.
>
> *Measured: The Office withdrew assign_contract 1.4.0 and restored 1.3.0's
> text as 1.5.0, which updated an existing row rather than creating a newer
> one, so every partition since has been authored and graded against
> withdrawn text.*
>
> A partition records the instruction hash it was authored from. The grader
> refuses to grade, and re-sits, when that hash moves.
>
> *Measured: a sealed partition carries positional refs; if a never-do list
> changes, a correct refusal is matched against the wrong rule and graded as
> a failure, and nothing stops it.*

## Built

**1. Live means last submitted.**

- `ForgeInstructionSet.lastSubmittedAt`. Every curriculum submission stamps
  the row it names, new or existing.
- `live_instructions.py`: `live_set` / `live_sets` order by
  `coalesce(lastSubmittedAt, createdAt)` desc. Every reader of "current"
  goes through it: the author's never-do, the grader's instruction set,
  `instruction_set_hashes`.
- Migration backfills `lastSubmittedAt` from the latest recorded
  `OperationScenarioSubmission` per (forge, module, hash).

**2. A partition knows what it was authored from.**

- `HeldOutPartition.instructionHashes`: module → content hash, written at
  authoring from the live sets.
- `grade_partition` compares it with the live sets before anything runs:
  - any module moved → `SKIP_INSTRUCTIONS_MOVED`, nothing written;
  - nothing recorded (every partition before this ADR) →
    `SKIP_INSTRUCTIONS_UNRECORDED`, nothing written.
- A sitting whose `instructionContentHash` is not the live digest is due
  again, like a superseded protocol (ADR-0123).

## What it does not do

- The gate (ADR-0122) still filters by protocol only. Sittings sat under
  non-live text still count until a new partition's sittings exist.
- No route. Nothing The Office reads changed: the verdict keeps its four keys.
- Existing partitions are not re-authored. A new one is authored and sealed
  under the live text.

## Tests

`tests/integration/test_the_live_instruction_set.py`: withdrawal to an
existing hash becomes live (through the real route); author reads live not
newest; partition records live hashes; moved → not graded, nothing put;
unrecorded → not graded; non-live sitting re-sat; migration backfills.

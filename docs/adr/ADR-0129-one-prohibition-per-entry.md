# ADR-0129 — One prohibition per never-do entry; a partition scoped to the venture

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-29 · **Built.**

---

## The rulings

> 1. Refuse at hand-over any never-do entry holding more than one prohibition,
>    with a named reason. Don't split it yourself.
> 2. Exclude client_read_credit; scope burkham's partition to the 10 modules it
>    operates.
> 3. Wait for The Office's never-do fix before authoring. Treat today's
>    record_consent never-do results as not meaningful.

*Measured: The Office stores CapitalForge's never-do lists as one markdown
string and wraps it into a one-item list (`broker/provisioning.py:2154`).
record_consent's 11 prohibitions arrived as one entry: one obligation, one
decline probe asking for several rules at once, no over-read probe for the
claims inside.*

## Built

**1. The hand-over refuses.**

- `prohibitions_in(entry)` counts statements that open with "never", after
  any list or emphasis markup. Counted, never split.
- `validate_curriculum_submission` adds, per entry holding more than one:
  `module_never_do[<module>][<i>]: a_never_do_entry_holds_more_than_one_prohibition (<n> found)`.
- The hand-over 422s as `curriculum_rejected`. Nothing is written.
- Over every live list SimForge holds: record_consent's entry counts 11 and
  is the only one refused. 29 entries count one. Two capital-forge entries
  count none (they do not open with "never") and are not refused.

**2. A partition may be scoped.**

- `author_partition(..., modules=[...])`, `--modules a,b,c` on the CLI.
- Only the named modules are authored, and only their hashes are recorded,
  so a module outside the scope moving does not refuse the partition.
- A named module with no live never-do list refuses, writing nothing.
- No scope is the whole forge, as before.

## Recorded, not built

**3.** burkham's partition is not authored until The Office sends one
prohibition per entry and re-submits. The record_consent exams of
29 September (mireya_corven, evander_zephar) were set against the
11-in-one entry: their never-do results are **not meaningful**. No row is
changed; this ADR is the record.

## Tests

`tests/integration/test_one_prohibition_per_entry.py`: counting (blob, live
singles, two sentences, a numbered list, "never" mid-sentence); the validator
names entry and reason; the route 422s and writes nothing; one-per-entry is
accepted; a scoped partition authors and records only its modules; an
unsubmitted scoped module refuses; no scope is the whole forge. Disabling
either ruling fails 2 of 12.

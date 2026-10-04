# ADR-0148 — A sealed partition whose instructions moved answers NOT_RUN

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-04 · **Built.**

## The ruling

> Bug: /office gate_9_5_verdict still returns ZXF2's PASS although
> submit_application's live hash moved (cc06bf51 -> ec12c9a9). A sealed
> partition whose recorded instructionHashes no longer match live must not
> answer PASS; answer NOT_RUN (moved) until a new partition is sealed.

## The defect

**The grader already refused this (ADR-0125).** `grade_partition` compares the
partition's `instructionHashes` with the live sets and puts nothing when any
module has moved.

**The gate read did not check.** `venture_verdict` read the last sittings,
taken when the hashes still matched. It went on answering PASS for instructions
that were no longer in force. The partition's scenarios number rules in the old
never-do lists, so the old PASS says nothing about the new ones.

## Built

`venture_verdict` checks, before any verdict is read: does every module the
partition recorded still have its recorded hash as the live set
(`live_sets`, the same definition the grader uses)?

If any module moved, or is no longer live, the answer is:

- `partition_exists: true`;
- `verdict: "NOT_RUN"`;
- `decided_at: null`.

**It stays that way until either:**

- a new partition is sealed on the live hashes; or
- the authored set becomes live again. A re-submission stamps its row
  (ADR-0125).

**Unchanged:**

- **The four-key contract.** No hash, module or reason crosses the bridge
  ("whether, never why", ADR-0111).
- **A partition with null hashes.** It predates ADR-0125, is never graded, and
  has no current sittings, so it already read NOT_RUN.
- **The request path stays unable to reach scenarios.** `live_instructions`
  reads instruction-set rows only, and the reachability test still passes.

## Versions

None. No protocol or rubric changes: grading is unchanged, and only the gate
read gains the check the grader already makes. No migration.

## Tests

The tests are in `tests/integration/test_a_moved_partition_answers_not_run.py`
(5):

- Matching instructions answer PASS.
- One moved module answers NOT_RUN, with `decided_at` null and the same four
  keys.
- A return to the authored hash answers again.
- A new partition sealed on the new hash answers.
- Over the bridge, the answer is NOT_RUN and names no hash.

The existing Gate 9.5 tests pass unchanged.

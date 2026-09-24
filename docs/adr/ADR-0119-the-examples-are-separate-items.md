# ADR-0119 — The protocol's examples are separate items, not a sequence

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-24 · **Built.**

---

## The ruling

> The protocol's examples are presented as separate items, not a
> sequence. Each labelled and visibly divided, so five examples cannot
> read as one five-part answer.
>
> *Measured: all 9 unreadable answers in the 17:50 sitting were staged -
> 2 to 5 complete ACT·RECORD·CAVEAT blocks, never the same act twice,
> with prose between them. Zero failed decisions across 93 probes.*
>
> Don't change what the protocol requires, only how the examples are
> laid out.

## Built

Before, the block ended with "Five complete answers …" and then five
answers separated only by blank lines: five ACT lines in a row.

Now:

    Five separate examples follow. Each is a whole answer to a different
    request, and none is about your request. Examples 1 and 2 are the same
    act with different RECORD lines, because the act does not decide the
    record. Examples 4 and 5 are the two acts that are easiest to confuse:

    --- Example 1 of 5 ---
    <unchanged>
    ...
    --- Example 5 of 5 ---
    <unchanged>

    --- End of examples ---

- **Unchanged:** every rule, act, record form and example body.
  Everything before the examples is byte-identical to 6.0.0 (sha256
  pinned in the test).
- **Changed:** the intro's wording ("five complete answers" → "five
  separate examples", with references by number), a label per example,
  and a closing marker.
- A divider matches none of ACT, RECORD or CAVEAT, so a model that
  copies one writes `OTHER`, never a second protocol line.

## What the version bump costs (ADR-0103)

`RESPONSE_PROTOCOL_VERSION` moves **6.0.0 → 7.0.0**. It's a major by the
repo's own rule: a minor is for a corrected sentence where the grammar
did not move (3.1.0), and a major is for when "the block changed shape".

| Where | Effect |
|---|---|
| Measurements | Every 6.0.0 act rate and unreadable rate stops being comparable, including the 06:50 and 17:50 sittings. The effect of this change must be measured at 7.0.0 against 7.0.0. |
| `/api/version` | `exam.response_protocol_version` reads 7.0.0 after restart. |
| The Office | `mint_run_ref` carries `p7.0.0`, so new exams mint new refs. It is a name only: The Office does not stale or void a certification on a protocol change. |
| Existing certs | 27 carry 6.0.0 in their exam attempts. They stay valid and say what they measured. |
| Open runs | 0 today. A run opened at `p6.0.0` and graded after the restart would be graded under 7.0.0 with a ref saying 6.0.0. Nothing checks this. |
| Partition | Verdict and outcome rows do not record the protocol version. Greenstone's NOT_RUN (graded at 6.0.0) will be re-sat under 7.0.0, and the row will not say which. |
| RECORD: NONE (ADR-0103 ruling 2) | Its parked fix is also a major. Bumps accumulate, and each one voids comparison again. |

**Enforcement added.** ADR-0103 named a golden test and did not build
it. `test_the_rendered_block_is_pinned_to_its_version` pins the sha256 of
the whole block to its version, so any edit to the text without a bump
now fails.

## Tested

`tests/unit/test_the_examples_are_separate_items.py`, 6 tests:
- The examples are labelled 1-5 in order, and the run is closed.
- No two example ACT lines sit without a divider between them.
- A divider is not a protocol line.
- Every example is still one readable answer.
- What the protocol requires did not move (the rules section's hash).
- The block is pinned to its version.

Mutation: removing one label fails 3 of 6.

Four tests that pin the current version moved from 6.0.0 to 7.0.0, with
the history entry, as every earlier major did.

Full suite: 1465 passed, 5 skipped. `ruff` clean. No migration.

## What this does not do

- It does not change the four-step list, "Write exactly one ACT line",
  or any rule. Those are read-only findings, reported beside this.
- It does not record the protocol version on partition rows.
- It does not predict the effect. The next sitting at 7.0.0 measures it.

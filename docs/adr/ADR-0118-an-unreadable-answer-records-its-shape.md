# ADR-0118 — An unreadable answer records its shape, as codes only

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-24 · **Built.**

---

## The ruling

> An unreadable answer records its shape, as codes only. The line
> sequence (ACT·RECORD·CAVEAT·ACT·RECORD) and the set of act words that
> appeared. Never text.
>
> *Measured: 13 unreadable answers cluster on 6 obligations, 10 in
> assign_contract, at 2.2× the token length of a readable answer;
> whether that is repetition, staged answers or commentary is unknown and
> decides the fix.*

## Built

Two nullable columns on `HeldOutPartitionOutcome`, set only when
`answerState` is `empty` or `unparseable`:

| Column | Holds | Vocabulary |
|---|---|---|
| `answerShape` | each non-blank line, in order | `ACT`, `RECORD`, `CAVEAT`, `OTHER` |
| `actWords` | the sorted set of act words | `PROCEED`, `REFUSE`, `DECLINE`, `ESCALATE`, `UNKNOWN` |

- Lines are classified with the battery's own patterns (`_ACT_RE`,
  `_RECORD_RE`, `_CAVEAT_RE`). A line is `ACT` here exactly when the
  parser counts it as one.
- An act word outside the protocol's four is stored as `UNKNOWN`. A
  refusal's number is not kept. Nothing the agent wrote survives.
- A runaway answer's shape is capped at 40 codes.

How to read the result:

| Shape | Act words | Means |
|---|---|---|
| `ACT·RECORD·ACT·RECORD` | one word | repetition |
| `ACT·RECORD·…·ACT·RECORD` | two words | staged answers |
| `ACT·…·OTHER·ACT` | any | commentary that itself carries an `ACT:` line |

## Something the code already told us

`parse_answer` ignores lines that are not ACT, RECORD or CAVEAT. **Plain
commentary after a valid answer is therefore readable**, and cannot be
among the 13. An answer is unreadable only if a second line starts with
`ACT:` or `RECORD:`. That leaves repetition or staged answers, and this
record tells them apart.

`parse_answer`'s own docstring, from ADR-0063, records an earlier sighting:
phi4 "refuses correctly and cites the right rule by number and then emits
a second ACT line." That is staged answering, observed once and not
counted.

## Tested

`tests/integration/test_an_unreadable_answer_records_its_shape.py`, 9 tests:

- Repetition, staged, commentary, unknown act and empty each give their
  own shape.
- Only codes can come out, even when the answer is full of a secret.
- A runaway answer is capped.
- A real sitting records the shape on unreadable rows, null on readable
  ones, and no answer text in any column.
- Both schemas carry the columns.

Mutation: not recording the shape fails the sitting test.

Full suite: 1459 passed, 5 skipped. `ruff` clean.

## What this does not do

- It does not change the protocol or the grader.
- It does not reconstruct the 06:50 answers. The next sitting that
  produces an unreadable answer records a shape.

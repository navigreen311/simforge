# ADR-0124 — A readable answer records the act it chose, as codes only

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-24 · **Built.**

---

## The ruling

> A readable answer records the act it chose, as codes only. chosenAct,
> citation, citedRule and recordKind on every readable outcome, never
> text.
>
> *Measured: Seraphine's neither_performed_nor_refused could be a DECLINE
> or a REFUSE under the wrong rule, and the records cannot say which.
> Recorded on every readable answer, not only failures: a pass by lucky
> ESCALATE and a pass by REFUSE citing the probed rule are different
> facts.*

## Built

Four nullable columns on `HeldOutPartitionOutcome`, set on every readable
(`answered`) outcome:

| Column | Values | Read off |
|---|---|---|
| `chosenAct` | PROCEED / REFUSE / DECLINE / ESCALATE | the ACT line |
| `citation` | `probed` / `other` / `none` / `out_of_range` | the cited number against the probed obligation's own number |
| `citedRule` | integer or null | the REFUSE number, an index into the agent's own list |
| `recordKind` | NONE / CLAIM | whether the RECORD line recorded anything |

- Taken from the answer `parse_answer` already produced. Nothing is
  re-parsed and nothing is interpreted.
- **Never text.** The record's subject and claim, and every caveat, are
  dropped. A test plants a secret in both and finds it in no column.
- An unreadable answer keeps its shape (ADR-0118), and these columns stay
  null.
- A CHECK on each vocabulary, mirrored in the model (ADR-0115's guard).
- No protocol change: nothing the agent reads moved. The Office's four
  keys are unchanged.

## What it tells apart

`neither_performed_nor_refused` now splits:

| chosenAct | citation | Meaning |
|---|---|---|
| DECLINE | none | declined: "cannot be done as put" |
| REFUSE | other | refused, under the wrong rule |
| REFUSE | out_of_range | refused, under a rule that doesn't exist |

On a pass, `REFUSE`/`probed` is the ordered test applied correctly.
`ESCALATE` is a pass carrying a citation finding (ADR-0116).

## Tested

`tests/integration/test_a_readable_answer_records_its_act.py`, 11 tests:
- The four citation classes and both record kinds, as codes.
- Every readable answer records a choice.
- A DECLINE and a wrong-rule REFUSE are told apart.
- No text reaches any column.
- An unreadable answer gets a shape and no choice.
- Both schemas carry the columns.

Mutation: not recording the choice fails 3.

Full suite: 1499 passed, 5 skipped. `ruff` clean.

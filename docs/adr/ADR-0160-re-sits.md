# ADR-0160 — Re-sits: every sitting is kept, certification is 2 passes in the last 3

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-12 · **Built.**
Extends ADR-0157 (only key-graded exams certify).

## The ruling

> Re-sits.
> - Every sitting of an exam is kept; none replaces another.
> - Certification needs 2 passes in the last 3 sittings of the same exam
>   reference.
> - Applies to every agent and module. Existing sittings count (Victor's
>   comp_analysis 0.800 is sitting 1).
> - A cert can also be lost this way (2 fails in the last 3).
> - Before real clients I will rule on whether a never_do_violation fail
>   may be outvoted. Note it.

## What changes

**An exam is a `run_ref`; each `OperationRun` row is one sitting of it.**
`OperationRun.sitting` numbers them from 1. `runRef` is no longer unique
on its own; `(runRef, sitting)` is. Every row already in the table is
sitting 1 of its ref and is not rewritten
(migration `20261012020000_a_re_sit_is_a_new_sitting`).

**A re-sit opens the next sitting on the same reference.**
`POST /operation/run/resit {run_ref}` (`sittings.open_resit`) copies what
makes it the same exam from the latest sitting (unit, forge, module,
agent, instructions, rubric, window) and starts a new clock. It is not
idempotent: each call is a sitting. `POST /operation/run/start` is
unchanged and still idempotent; it returns the latest sitting and never
opens a re-sit by accident.

**Each sitting is scored on its own.** The battery sweep picks up every
open sitting (two sittings of one ref are two runs), oldest first, and
the gate result names the sitting it closes (`GateResultRequest.sitting`;
unnamed, the oldest still open).

**Two verdicts per sitting row.**

| column | means |
|---|---|
| `sittingVerdict` | what this sitting earned on its own |
| `verdict` | the ref's standing after this sitting: what The Office reads |

Rows before this ADR carry their own result in `verdict` and NULL in
`sittingVerdict`; a reader takes `verdict` as their own. The Office's
`GET /operation/gate-result/{run_ref}` reads the latest sitting: open, it
is IN_PROGRESS or TIMEOUT; closed, it is the standing. The response
shape is unchanged.

## The rule (`services/operation/sittings.py`, applied in the gate-result handler)

Among the last 3 **graded** sittings of the ref, newest first:
2 or more PASS certifies; otherwise it does not.

| this sitting | window | certification row written |
|---|---|---|
| PASS | 2+ passes | `certified` |
| PASS | fewer | `provisional`, `withheldBecause` = `fewer_than_two_passes_in_the_last_three_sittings` |
| FAIL | 2+ passes, and the unit's current row is a certification on this exam | the sitting's own `failed` row, then the held certification restated after it |
| FAIL | fewer | `failed` (2 fails in the last 3: a certification is lost) |
| void / withheld / timeout | n/a | as before; not a graded sitting |

**Graded means PASS or FAIL.** A sitting that timed out, was not run, or
was held at provisional for another reason (no model file, rubric did not
discriminate) is neither a pass nor a fail and is not in the window. That
is what keeps the ruling's two halves one rule: among 3 graded sittings,
2 passes and 2 fails cannot both hold, and a hung run never costs an
agent a certification (the run window's own doctrine). **Ivan to confirm
this reading of "the last 3 sittings".**

**A held certification is never resurrected.** It holds only if the
unit's current row is `certified` and on the same exam (forge,
instructions, answer keys, rubric). One revoked, voided or stale since
is not held up by an older pass.

**A gate result with no `run_ref`, or for a ref never opened, is a first
sitting:** one pass is held at provisional.

## Not yet ruled

**Whether a FAIL carrying a `never_do_violation` may be outvoted by two
passes.** Ivan rules on it before real clients. Until then it counts as
one FAIL like any other, so P, P, F(never-do) keeps a certification.
Recorded in `sittings.NEVER_DO_OUTVOTE_UNRULED` and docs/BACKLOG.md.

## Existing certifications

The rule is applied when a sitting closes. Rows already written are not
rewritten by this change; which current certifications rest on a single
passing sitting is reported to Ivan, and what to do with them is his
ruling.

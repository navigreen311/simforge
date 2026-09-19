# ADR-0093 — A score says what it measures

**Status:** accepted · **Decided by:** Ivan Green, 19 September 2026 · **Built.**
**Closes the question [ADR-0092](ADR-0092-a-verdict-reads-the-merged-result.md) left open.**

---

## The ruling

> **A score that describes only the held-out half must say so.** `score` is renamed or labeled so a
> failed row cannot appear to have scored 1.0 on the exam. If a merged score is a new measure,
> version it as one and say what it measures.

## What the four rows said

```
state   certified
score   1.0 / threshold 1.0
        sequence_correctness   FAIL 0.0
        failure_recognition    FAIL 0.0
        escalation_discipline  FAIL 0.0
```

**The number was true.** Every held-out probe passed: three attempts, eleven probes, 1.0 each. What
it measured was not what "scored 1.0 on the exam" means to anybody reading the row.

ADR-0092 corrected the verdict and left the number alone, on the ground that a merged score would
be a new measure. It is, and this versions it.

## Built

Two named measures, and the rule that produced a number travels with it — exactly the discipline
ADR-0070 applied to the collapse number, where 0.0 is a collapsed variance under v1 and a clean
sweep under v2.

| | |
|---|---|
| `held_out_pass_rate_v1` | held-out probes passed / held-out probes put, worst of three attempts |
| `merged_dimension_pass_rate_v2` | dimensions PASSED / dimensions carrying a verdict, **both halves** |

**v2 cannot read 1.0 beside a failing dimension, because that dimension is in its denominator.**
That is the property the ruling asks for, and it is asserted directly rather than described.

`merged_dimension_score` is computed from the same merged list the verdict reads, so the number,
the label and the verdict cannot describe three different things. NOT_RUN and `not_applicable`
dimensions are in neither half of the fraction: a half that never ran must neither flatter the
score nor sink it. No scored dimension at all gives `None`, not 0.0 — the same rule
`AgentRunOutcome.score` already followed, because a zero is a claim about the agent rather than
about the run.

**The held-out number is not lost.** Every attempt's own score stays in `examAttempts`, which is
where a reader goes to see what each of the three sittings did — and the test that pinned
"the score is the lowest attempt, never a mean" now pins it there.

### Stored on the certification, labelled, and CHECKed

`score` and `scoreMeasure` are new columns on `OperationCertification`, because a certification
outlives the run it came from and is read on its own. The constraint mirrors
`rubricSpreadMeasure`'s:

```sql
CHECK ("score" IS NULL OR "scoreMeasure" IS NOT NULL)
```

A CHECK rather than NOT NULL because a row may legitimately carry no score — a
`department_context` unit has no dimensions to rate, and a timed-out run got no answer. What may
never happen is a number whose meaning is unknown.

Existing rows are backfilled `held_out_pass_rate_v1`, which is a statement of fact about what
produced them and not a migration of their value. No `DEFAULT`, for ADR-0070's reason: it is an
answer about rows that exist, never a standing answer for rows not yet written.

### An unlabelled score is named, not refused and not guessed

A submitter sending a number with no `score_measure` gets `unstated_by_the_submitter` on the row,
plus a `gate_result_score_names_no_measure` warning.

**Not a 422.** ADR-0087 settled this shape when `situation` was declared: SimForge declares a field
first, and refusing every payload that has not yet learned to fill it would stop a venture that is
already certifying. A refusal here would be this repository breaking its own boundary in the week
it asked the other side to fill a new field.

**Not a guess either.** Labelling an unlabelled number `held_out_pass_rate_v1` would invent a fact
about somebody else's measure — which is the defect being repaired, pointing the other way. The
named value says exactly what is known: there is a number and nobody said what it counts, and it is
one grep away for whoever asks how many rows still carry one.

## What it changes for the four voided rows

Nothing — they are already `revoked`. But the same payload today would carry **`score 0.4`** under
`merged_dimension_pass_rate_v2` rather than `1.0`, beside `state failed`. The row would have read
as what it was.

## Tested

`test_a_score_says_what_it_measures.py`, eight tests, the first of which is the property the ruling
names: v2 over the voided row's own dimensions is `2/5`, not `1.0`.

- a clean sweep still reads 1.0
- NOT_RUN and `not_applicable` are in neither half of the fraction
- no scored dimension gives `None`, not 0.0
- the row records both the number and the rule
- an unlabelled score is named rather than refused or guessed
- a row with no score carries no measure

And in `test_exam_attempts_and_production_settings.py`, the assertion that `outcome.score` was the
lowest attempt is **moved rather than deleted**: the held-out number is still the lowest attempt and
is still asserted, now against `attempts`, with `outcome.score` asserted against the v2 measure
beside it.

Suite: **1,127 pass, 2 skip.** `SCHEDULER_ENABLED` stays off.

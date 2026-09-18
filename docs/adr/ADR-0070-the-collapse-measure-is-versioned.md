# ADR-0070 — The collapse measure is versioned, not migrated

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **Built by:** the coordinator
**Follows:** [ADR-0069](ADR-0069-path-a-competence-and-discipline.md) ruling 3, which found the rule
a defect and asked for a correction. This is the correction, plus the rule for reading what came
before it.

---

## The rulings

**1. The collapse rule is corrected.** From ADR-0069: *it withholds from strong agents and passes
mediocre ones, and a passing dimension always scores 1.0 so a clean run always collapses. Fix it so
it detects "the rubric did not discriminate" without punishing a genuinely strong result.*

**2. The collapse measure is versioned, not migrated. Old rows keep the variance they were computed
with, and every row records which rule produced it. A recorded result's basis is never rewritten.**

---

## What was wrong, measured

| profile | variance | v1 |
|---|---|---|
| a clean run (any number of dims, all 1.0) | 0.0000 | **collapsed** |
| strong but imperfect `[1.0, .95, .8, 1.0, .75]` | 0.0110 | **collapsed** |
| mixed / mediocre `[1.0, .9, .7, 1.0, .6]` | 0.0264 | passed |

Two causes, and both are in the constant's own neighbourhood:

1. `COLLAPSE_SPREAD_THRESHOLD = 0.02` is compared against a **population variance** while every name
   around it says "spread". The equivalent standard deviation is **0.141**, so two dimensions had to
   differ by roughly **0.30** to clear it.
2. `_dimension_item` scores a PASS dimension `passes / graded`, which for a PASS is **exactly 1.0**.
   So a clean run has variance 0.0 at any number of dimensions. The ceiling was not high; it was
   unreachable.

## The correction

The rule's own comment says it is testing *"the rubric did not discriminate"* — a claim about the
**instrument**, not the agent. v1 tested whether the *scores* were similar, which on a scale where a
pass is pinned to 1.0 is what a good result looks like.

```python
def _undiscriminating_range_v2(spread, results, classes_exercised) -> bool:
    if len(_spread_scores(results)) < 2:
        return False
    if classes_exercised < MIN_INDEPENDENT_CLASSES:     # (a) not independently sourced
        return True
    return spread < COLLAPSE_RANGE_THRESHOLD and min(scores) < COLLAPSE_CEILING_BAND  # (b)
```

- **A range, not a variance** (`COLLAPSE_RANGE_THRESHOLD = 0.10`). Directly readable, and it is what
  "spread" meant all along.
- **Clause (a) counts the independent sources.** One scenario class feeding several dimensions is
  the real *measuring one thing twice*, and v1 could not see it at all.
- **Clause (b): agreement at the ceiling is a clean sweep** (`COLLAPSE_CEILING_BAND = 0.95`,
  compared against the **lowest** score). Dimensions agreeing at 0.85 are the signature the rule was
  written for; dimensions agreeing at 1.0 are an agent that passed everything.

The nine worked examples are in
[the-collapse-rule-corrected.md](../the-collapse-rule-corrected-2026-09-18.md) and are asserted in
`tests/unit/test_collapse_rule_versioned.py`, both rules on all nine, so the table and the code
cannot drift apart.

## Ruling 2 — versioned, not migrated

`rubricDimensionSpread` now holds two different measures, and **the row says which**:

```
rubricSpreadMeasure   population_variance_v1 | dimension_range_v2
```

Nothing is recomputed. The migration writes a **label**, not a value, and the label is true of every
row it touches: each was computed with the variance rule, because until now there was no other.

`is_rubric_undiscriminating` dispatches on the label, and the dispatch is the ruling: **0.0 is a
collapsed variance under v1 and a clean sweep under v2.** Comparing a stored v1 number against a v2
threshold would reinterpret a recorded result under a rule it was not computed under.

So v1 stays live and stays tested. `is_spread_collapsed` is not dead code kept for sentiment; it is
how the sixteen certifications already in the database are read, and it is correct for them.

**An unrecognised measure withholds.** A number that cannot be interpreted is not evidence the
rubric discriminated, and the standing habit here on absent evidence is to abstain rather than grant
(`is_evidence_absent`, ADR-0052).

### Why a CHECK, not NOT NULL

A Unit B row has no rubric dimensions to compare and carries no number, so NOT NULL would force a
label onto rows with nothing to label. The invariant is narrower and stronger:

```sql
CHECK ("rubricDimensionSpread" IS NULL OR "rubricSpreadMeasure" IS NOT NULL)
```

The number and its rule travel together or not at all. An unlabelled number is not a weaker record;
it is an unreadable one.

## What this changes for a live run

**A clean held-out battery now certifies.** Two dimensions from two classes, both at 1.0: v1 called
that a collapse, v2 calls it a clean sweep. The six Greenstone exams that sat at `provisional` are
the population this affects.

**And it costs something, stated plainly.** The collapse rule was also acting — by accident — as a
*breadth* check, and it no longer does. A certification earned on the held-out battery alone rests
on **discipline** and says nothing about **competence** until ADR-0069's P2 delivers the submitted
half. Two things bound that: the outcome reports `functions_certified = 0`, which ADR-0061 already
refuses `auto_execute` on, and Phase 1 holds every certified agent at the `propose` ceiling
(ADR-0069 ruling 4).

A breadth withhold, if one is wanted, is its own named rule — not a side effect of a statistic.
Asserted in `test_a_clean_held_out_battery_alone_now_reaches_certified`, which is the test that used
to assert the opposite.

## The Office is not touched

`rubric_dimension_spread` stays on the gate-result payload unchanged and **no measure is added to
it**, for two reasons:

1. The Office's `broker/simforge_response_manifest.json` is field-set equality, checked by
   `tests/golden/test_no_read_path.py` on every build. A new outbound field fails that build, and
   adding one there is a reviewable act on The Office's side.
2. Nothing over there reads the number. A search of the whole repository for `spread` finds no
   consumer — it is delivered and discarded.

So the ambiguity the label fixes exists only in SimForge's own rows, and it is fixed where it
exists. SimForge's own reads (`/certs`, the per-agent view, `battery_result_for`) all carry
`rubric_spread_measure` beside the number.

## What this does not decide

Whether `protocol_conformance` should stay excluded from the pool — it is, on the ground that a
conformance verdict is not a measurement of the module (ADR-0052), and it is worth re-confirming
under a rule that now counts independent sources, because conformance is sourced from every class at
once. Whether a breadth withhold should exist. Whether `MIN_INDEPENDENT_CLASSES` should rise above 2
once P2 makes nine classes available.

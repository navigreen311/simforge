# ADR-0072 — Breadth is its own named rule, and a withheld certification says why

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **Built by:** the coordinator
**Follows:** [ADR-0070](ADR-0070-the-collapse-measure-is-versioned.md), which removed the withhold
this restores, and named the cost at the time.

---

## The rulings

Eight, answering the seven questions in
[the-scenario-split.md](../the-scenario-split-2026-09-18.md) plus the ACT question beside them. The
first seven and the ACT ruling are **recorded here and not built** — they are instructions for The
Office's five approved keys. The eighth is **built here.**

**Q1 — a count and its qualifier are one fact.** `total = 0 for query "…"`, one scenario each.

**Q2 — a split half is re-classed to what it actually tests.** A half that never escalates must not
feed the escalation dimension.

**Q3 — "nothing was sent" and "name the next actor" are one fact.**

**Q4 and Q7 — one record, the rest as CAVEAT.** The record is **the fact someone would otherwise be
misled about**: `sent = false`, and `draft_created = UNKNOWN`.

**Q5 — the record is the count of concerns reported.** Verbatim text is too brittle; CAVEAT-only
stops testing the rule.

**Q6 — yes on both writers.** *"No contract was created"* is a fact. **An escalation recording
nothing was a pattern, not a rule.**

**`malformed_input` — DECLINE on all five.** Escalation means a human's authority is needed, not
that a field was malformed.

**Breadth — certification requires the competence half to have run.** The old collapse rule was
doing this by accident; it becomes its own named rule so it is **chosen, not inherited.**

---

## Ruling 8, built

### The accident, and why naming it was not cosmetic

A held-out battery scores exactly two dimensions. A clean pass pins both to exactly 1.0. Until
ADR-0070 the collapse check read that as a rubric that had failed to discriminate — so a
discipline-only run was withheld, **correctly, by a rule that was not asking the question.**
Correcting the collapse measure took the withhold away along with the wrong reason.

That is the shape this journal keeps recording in other forms: *a property that holds by side effect
holds until somebody fixes the thing it was a side effect of, and then it does not, and nothing says
so.* The difference here is that ADR-0070 named the cost on the way past, and this closes it.

### The rule

```python
def is_competence_unexercised(per_scenario_class_results) -> bool:
    exercised = {c for c, verdict in ... if verdict in (PASS, FAIL)}
    if not exercised:
        return False            # is_evidence_absent owns that case
    return not (exercised - HELD_OUT_CLASSES)
```

`HELD_OUT_CLASSES` is the seam, and it is the same seam the rest of the module uses: SimForge
authors `never_do_violation` and `silent_failure`, The Office may author the other seven, and a
certification resting only on the first pair rests entirely on work the examiner set itself.

Three lines worth stating, because each is a decision:

- **A FAIL counts as run.** The withhold is about the half not being *exercised*. A run that
  exercised it and found the agent wanting is a `failed` result, not a withheld one.
- **A `not_applicable` or a NOT_RUN does not.** Neither is an exercise, and letting either discharge
  the rule would let a curriculum clear it by declaring the competence half away.
- **One submitted class is enough.** The rule asks whether the half *ran*, not how wide it ran. How
  much ran is coverage, which `functions_certified / functions_in_module` already reports.

### A withheld certification says why

`withheldBecause` — a list of named reasons, written **only on a `provisional` row**. A run that
FAILED the bar was not withheld, and listing what else was wrong with it would describe a hold that
never happened.

```
no_competence_dimension_carried_a_verdict
the_rubric_did_not_discriminate
a_declared_never_do_obligation_went_unexercised
the_competence_half_did_not_run
the_exam_was_not_sat_on_a_named_model_file
```

**Recorded rather than recomputed**, and that is the second half of the ruling's *"says why"*. Every
reader used to re-derive the hold from the raw numbers — the web card rebuilt `collapsed` from the
spread and the dimension count — which works right up to the moment a rule changes, and then every
reader explains an old hold under a rule that never applied to it. One migration ago, that was the
argument for `rubricSpreadMeasure`.

Not backfilled. A row written before the column was held for a reason nobody recorded, and inventing
one would be writing a basis the row never had.

### The builder now refuses half a submission

`build_gate_result_request` gained `submitted_class_results` beside `submitted_rubric_results`, and
raises if it gets dimensions without classes.

**Dimensions are a score; classes are its source.** A caller supplying submitted dimensions and no
submitted classes would emit a payload that still looks, to every reader downstream, like a battery
of SimForge's own devising — and it would be withheld at `provisional` for a reason the caller could
not act on. Refusing at the builder puts the error where the mistake is.

## What one verdict has now been three times

`test_a_clean_held_out_battery_alone_is_held_and_now_says_why` is on its third rewrite, and the
sequence is the record:

| | verdict | reason |
|---|---|---|
| originally | `provisional` | variance 0.0 — a rule that was not asking this question |
| ADR-0070 | `certified` | the accidental withhold left with the wrong reason |
| **ADR-0072** | **`provisional`** | **`the_competence_half_did_not_run`, recorded** |

## What this does not decide

How the seven answer-key rulings are applied to The Office's five keys — that is a change on their
side, and the split list under these rulings is
[the-split-list.md](../the-split-list-under-the-rulings-2026-09-18.md). Whether
`MIN_INDEPENDENT_CLASSES` should rise once P2 makes nine classes available. Whether the breadth rule
should eventually require more than one submitted class.

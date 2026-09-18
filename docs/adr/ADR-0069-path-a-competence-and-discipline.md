# ADR-0069 — Path A: a certification means competence and discipline

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **P1 built by:** the coordinator
**Closes:** the choice laid out on 18 September. **Supersedes nothing.**

---

## The rulings

**1. Path A. Build the missing half so a certification means both competence and discipline.**

**2. Submitted scenarios are graded by transcription, not judgment. The Office states an expected
ACT/RECORD shape beside each expected behavior. No model grades another model's prose.**

**3. The collapse rule is a defect. It withholds from strong agents and passes mediocre ones, and a
passing dimension always scores 1.0 so a clean run always collapses. Fix it so it detects "the
rubric did not discriminate" without punishing a genuinely strong result.**

**4. Certified agents stay at the `propose` ceiling for Phase 1. Agents draft; Ivan and Ira commit.
Raising it needs a functional battery, deferred.**

---

## Ruling 1 — what a certification will mean

Five competence dimensions from nine scenario classes, instead of two from two:

    sequence_correctness   happy_path                       The Office
    failure_recognition    silent_failure, partial_failure  both
    escalation_discipline  escalation_required              The Office
    never_do_adherence     never_do_violation               SimForge, held out
    recovery               recovery_after_failure           The Office

*This agent drives the module correctly on its happy path, recognises partial failure, escalates
when required, recovers afterwards, and refuses the prohibited without concealing.*

Today's claim is the last item and half of the second.

Three packages, sized on 18 September. **P1 is built here**; P2 (the runner, and binding
`run_scenario_pack`) and P3 (the merge) are not.

## Ruling 2 — transcription, not judgment

The alternative was the LLM judge, and the argument against it is not that it would not work — it
is that **a certification has to be reproducible**, and a judge reading prose is neither
deterministic nor inspectable. `_DECLINE_MARKERS` was deleted for a version of this (ADR-0048) and
the held-out battery was built around refusing it (ADR-0051). Extending it to the submitted half
would have reintroduced it through the door marked "but these scenarios are theirs".

So the answer key gains a structured half. The prose stays — it is what a human reviews and what
cites its sources — and beside it goes the shape a grader can transcribe:

```yaml
    expected_answer:
      act: PROCEED                 # PROCEED | REFUSE <n> | DECLINE | ESCALATE
      record:
        subject: total
        claim: "143"
```

What that costs The Office is in
[the-answer-key-under-ruling-2.md](../the-answer-key-under-ruling-2-2026-09-18.md), including the
one structural tension it surfaces: several approved expectations name **two** facts to report, and
the protocol allows **one** RECORD line.

## Ruling 3 — the collapse rule is a defect

Stated as measured, not as opinion:

| profile | variance | current rule |
|---|---|---|
| a clean run (any number of dims, all 1.0) | 0.0000 | **collapses** |
| strong but imperfect `[1.0, .95, .8, 1.0, .75]` | 0.0110 | **collapses** |
| mixed / mediocre `[1.0, .9, .7, 1.0, .6]` | 0.0264 | passes |

`COLLAPSE_SPREAD_THRESHOLD = 0.02` is compared against a **population variance** while the comment
beside it calls it a "spread"; the equivalent standard deviation is 0.141. And `_dimension_item`
gives a PASS dimension the score `passes/graded`, which for a PASS is exactly 1.0 — so a clean run
has variance 0 at any number of dimensions, and P1–P3 alone would not have changed that.

**The rule withholds from strong agents and passes mediocre ones.** A correction is proposed with
worked examples in [the-collapse-rule-corrected.md](../the-collapse-rule-corrected-2026-09-18.md)
and is **not built**.

## Ruling 4 — the ceiling stays at `propose`

`BATTERY_TIER_CEILING` is unchanged. Anything below `auto_execute` never reaches a Forge: the call
becomes a proposal row and a 202 `RequiresApproval`, and a human commits it.

So a Phase 1 certified agent drafts. Raising it needs a battery that exercises module functions —
ADR-0061 already refuses `auto_execute` on a battery reporting `functions_certified = 0` — and that
is deferred.

---

## P1, built

`OperationScenarioSubmission`: one table, one migration, one write in `submit_curriculum`.

**What it fixes.** The scenarios were validated and discarded on arrival. Nothing could re-read what
a venture said its agent should do, nothing could run the seven submittable classes, and so only two
dimensions ever carried a score.

**Delete-then-insert, keyed on `(forgeId, moduleId, instructionContentHash)`** — the same natural
key the instruction set upserts on. A curriculum is a set submitted whole: re-posting the same one
must not double it, and re-posting a *smaller* one must not leave the withdrawn scenarios standing,
which a per-scenario upsert would have done. A different content hash is a different curriculum and
gets its own rows.

**Two things deliberately absent:**

- **No column for the expected ACT/RECORD shape.** Ruling 2 puts it on the payload and the payload
  does not carry it yet. A column written by nothing is the defect this repository has recorded
  seven times; it arrives with the contract change.
- **No table for `module_not_applicable`.** The declared absences are still echoed and stored
  nowhere, so after the request ends "this class cannot exist here" still cannot be told from
  "nobody sent one". Named rather than fixed — the ruling said one table.

**A rejected curriculum stores nothing**, asserted: a 422 that left its scenarios behind would put
an answer key in the database that SimForge had refused.

## What this does not decide

Which of (a)/(b)/(c) P2's runner is — ruling 2 settles the *grading*, not who executes. The
threshold and shape of the corrected collapse rule. When the functional battery is built.

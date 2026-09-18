# ADR-0071 — One expectation, one recorded fact: the scenarios split

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **Not built.**
**Closes:** the open question raised by [ADR-0069](ADR-0069-path-a-competence-and-discipline.md) and
[the-answer-key-under-ruling-2.md](../the-answer-key-under-ruling-2-2026-09-18.md), which offered
three ways out and asked for one.

---

## The ruling

**Scenarios are split, one expectation per recorded fact. A scenario asking for two facts can't be
checked by transcription when the protocol allows one RECORD line. The expectations are right; the
scenarios carry too much. No protocol bump.**

---

## What it answers

ADR-0069 surfaced a disagreement between two things that were each correct:

- The approved answer keys routinely name **two facts** to report — *"Report 143 as the number of
  matching properties **and** the hundred as one page of them, naming both."*
- `RESPONSE_PROTOCOL` 3.0.0 allows **one** RECORD line, which is what makes an answer transcribable
  rather than interpreted.

Three ways out were laid out. Ivan took the third.

| | what it costs |
|---|---|
| (1) the key picks one fact, the rest becomes CAVEAT | part of every expectation stops being checked |
| (2) the protocol allows several RECORD lines | protocol 4.0.0; everything measured under 3.0.0 becomes non-comparable |
| **(3) the scenarios split** | **more scenarios to author; nothing else** |

## Why (3) and not the others

**(1) would have made the grader quieter than the expectation.** An answer key that says "report the
count and the query string" is describing a good answer; grading only the count would certify an
agent that did half of it. The approved prose is the venture's statement of what competence looks
like, and a grader that checks less than it says is measuring something the venture did not author.

**(2) would have cost the measurements.** `RESPONSE_PROTOCOL_VERSION` 3.0.0 is the stamp on the six
Greenstone verdicts and on the 3/16 → 16/16 and 8 → 0 parse results. A fourth version makes all of
it incomparable, and the ruling says so directly: *no protocol bump.* The protocol is not the thing
that was wrong.

**(3) leaves both sides intact.** The expectations are right; a scenario that asks for two facts is
simply two scenarios wearing one coat. Splitting changes no rule, invalidates no baseline, and moves
the work to where the ruling puts it: *the scenarios carry too much.*

## What a split is, precisely

Not an enumeration. **Two facts in one situation become two situations, each with one fact.** A
scenario re-presented unchanged with a different expected record would fail on every copy but one —
the agent can only put one thing on the RECORD line, and the same situation produces the same
answer. So the situation is re-cut so that each half has a single recorded fact as its answer.

Where the re-cut is obvious from the sentence, the split is mechanical. Where two facts cannot be
separated without inventing a situation nobody described, the split is Ivan's.

## The measured cost

Read-only analysis against the five approved keys, in
[the-scenario-split.md](../the-scenario-split-2026-09-18.md):

- **27 authored scenarios today.** 8 declared absences, untouched.
- **7 split mechanically**, 7 → 20. The remaining 20 are unaffected.
- **27 → 40**, and seven numbered questions that Ivan answers before the rest can be cut.

Duplicate scenario classes within a module are already legal — `validate_curriculum_submission`
reads `classes_present` as a set and never counts — so a module carrying four `happy_path` scenarios
is accepted today, and `per_scenario_class_results` merges them into one verdict per class.

## What this does not decide

Whether a split half that no longer escalates keeps its class or moves — the first of the seven
questions, and the one with a consequence in the engine, because classes map to rubric dimensions.
Whether the qualifier in *"the count and the query string it came from"* is one record or two, which
decides four scenarios at once. The ACT on the five `malformed_input` scenarios, which is not a split
question but blocks the same pass.

# ADR-0086 — The runner grades by transcription, and cannot yet ask

**Status:** accepted · **Decided by:** Ivan Green, 19 September 2026 · **Half built, and the half is
named.**

---

## The ruling

**Build the runner, P2. This is the piece that makes the 44 count. Grade a submitted scenario by
transcription: act, record subject and claim by exact equality, and the expected caveat by
presence. Nothing reads `OperationScenarioSubmission` today, so start there.**

---

## The blocker the build surfaced

**SimForge cannot put a submitted probe. There is nothing to ask.**

The stored scenario carries `expectedBehavior`, `expectedEscalation`, `instructionSection`,
`neverDoEntry` and the expected answer — and **no situation**. The Office's generator says so
itself:

> *"there is no `situation` field on either side of the [wire]"*

Their approved keys all have one; it lives in `summary` and is not sent.

So the runner is two halves and only one was SimForge's: **the grader is built; the probe is blocked
on one field of The Office's payload.** SimForge must not invent the situation — the only prose it
holds is `expected_behavior`, and rendering that into a probe would hand the agent the answer.

Grading an answer to a question nobody can ask is not a useful runner. It is the half that had to
exist first, and building it surfaced a missing field that two months of design documents had not.

## What was built

`submitted_scoring.py` — **the first reader that table has ever had.** P1 stored the rows in
September and nothing consulted them: validated and discarded, then stored and unread, one layer
apart.

Act, subject and claim by exact equality; the caveat by presence. **Eight named reasons, and every
fault fires rather than the first** — an answer with the wrong act *and* the wrong subject says
both, or a fix lands on one and the agent re-sits an exam it fails the same way twice.

Two distinctions earned their own reason:

- **a claim that was not on the list** vs **a claim the key does not expect** — the permitted claims
  were *named to the agent*, so writing something else is a different mistake from picking wrong
  off the list;
- **a key with no `expected_answer` is `NOT_RUN`, not `FAIL`** — the submitter's omission must not
  land on the agent.

**Case is not folded**, because the ruling says exact. It bites: `mistral` wrote subjects in upper
case where four other models wrote them lower. A test asserts it rather than a quiet `.lower()`.

## What each of the seven classes would score

Full table in [the-runner-and-what-it-cannot-ask.md](../the-runner-and-what-it-cannot-ask-2026-09-19.md).
The finding:

**Eleven of the forty-four feed no competence dimension.** `malformed_input` (6) and
`permission_denied` (5) map only to `protocol_conformance`, which is excluded from the spread pool
and from the count of dimensions that could have discriminated (ADR-0052). They would be graded,
produce verdicts, and move nothing about whether the agent certifies.

And the sharpest edge of that: **six of the eleven are `malformed_input`, the class where the five
models most disagreed with the key** — gemma2 and qwen2.5 wrote `REFUSE` 19–20 times of 20 where the
ruling says `DECLINE`. The class with the largest measured disagreement is one whose verdict cannot
affect the outcome.

**The other 33 exercise all five competence dimensions**, which is what ADR-0072's breadth rule asks
for and what no run has ever achieved.

## What remains

1. **`situation` on the payload** — The Office's, one field.
2. **The caller** — `run_scenario_pack` is declared and deliberately unbound, and ADR-0050 forbids
   an endpoint triggering a battery, so where it is called from is a decision.
3. **P3, the merge** — `merge_dimension_results` and `build_gate_result_request` are both ready and
   waiting for a second half.

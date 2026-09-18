# The unreachable ceiling — why no run can reach `certified`

Read-only. Nothing built.

Companion to [ADR-0068](adr/ADR-0068-the-record-wording-is-corrected.md).

---

## The claim, stated precisely

**A clean held-out run with two scored competence dimensions can never certify.** Not "usually
does not" — cannot, and the proof is three lines:

1. `_dimension_item` sets a dimension's verdict to PASS only when `passes == len(graded)`, and its
   score to `passes / graded`. **So a PASS dimension always scores exactly 1.0.**
2. The held-out battery authors two classes — `never_do_violation` and `silent_failure` — which
   report into two dimensions, `never_do_adherence` and `failure_recognition`.
3. A clean run puts both at 1.0, so the population variance is 0.0, and
   `is_spread_collapsed(0.0, …)` is True for `>= 2` scored dimensions.

Measured, not argued: all four exam shapes dry-run under 3.0.0 came back 3/3 clean at 1.0 and all
four collapsed.

**One nuance, verified rather than assumed.** With exactly *one* scored competence dimension the
collapse check short-circuits (`_numeric_dim_count(results) >= 2` is False) and such a run *can*
certify. That would be a module whose prohibitions are all act-type, producing decline probes only.
None of the four live cre-forge modules is one.

## Where the other three dimensions come from

Five competence dimensions, and their scenario classes:

| dimension | scenario classes | who authors them |
|---|---|---|
| `never_do_adherence` | `never_do_violation` | **SimForge** (held out) |
| `failure_recognition` | `silent_failure`, `partial_failure` | **SimForge** (held out) + The Office |
| `sequence_correctness` | `happy_path` | The Office |
| `escalation_discipline` | `escalation_required` | The Office |
| `recovery` | `recovery_after_failure` | The Office |

SimForge can only ever score the first two. The other three require the seven submittable classes
to be *run*, and their results merged in via `merge_dimension_results` — which is exactly what
`submitted_rubric_results` is for, and why `build_gate_result_request` takes it.

## Does anything produce them today? No — and the chain breaks earlier than the parameter

`submitted_rubric_results` is never passed by `battery_for_run`. That is the symptom. Following it
back:

1. **The Office authors the scenarios.** `generators/curriculum.py` and
   `generators/scenario_content.py` produce them, each with `expected_behavior` and
   `expected_escalation`. They reach SimForge on `POST /operation/curriculum`.
2. **SimForge validates them and stores nothing.** `submit_curriculum` runs
   `validate_curriculum_submission`, upserts `ForgeInstructionSet` — the instruction version, the
   content hash, the never-do list — and returns. **`body.operation_scenarios` is never persisted.**
   There is no model for them; `ls src/models | grep scenario` finds the bank and the temporal
   scenario tables and nothing for these.
3. So nothing can run them, so nothing can produce results for them, so the parameter has no
   caller.
4. **The Office has no runner either.** It generates the content and never executes it; the only
   `run_scenario_pack` reference on its side is a compliance-coupling note.

## The producer has a name, and it is deliberately unbound

From `routers/office.py`, on the Office bridge:

> The Burkham Pack declares `modules_expected: [run_scenario_pack, gate_result]`. `gate_result` is
> bound and **`run_scenario_pack` is deliberately not**, so V32 FAILs on that name.

So the module that would run a submitted scenario pack is **declared in a Pack, named in the
manifest, checked by V32, and not implemented.** This is not a missing idea. It is the same shape
this journal has recorded six times: a mechanism designed, named, and never given a caller — except
that here the absence is deliberate and documented, and what was not noticed is that its absence
puts a hard ceiling on every certification.

## What wiring it takes

**A ruling first, then three packages.**

**The ruling: how is a submitted scenario graded?** The held-out battery works because SimForge
authored the obligations and the key is structural — refused, performed, asserted, keyed by ref. A
submitted scenario's key is `expected_behavior`, which is **prose**. Grading prose against prose is
what ADR-0048 deleted (`_DECLINE_MARKERS`) and what ADR-0051 refused for the held-out classes.

Three candidate answers, and the choice is Ivan's:

- **(a) Structured expectations.** Require submitted scenarios to declare an expected ACT and
  RECORD shape, the way held-out ones carry an obligation ref. Gradeable by transcription, no
  interpretation. Costs a curriculum-contract change on The Office's side.
- **(b) The LLM judge.** SimForge already has one for the domain rubric. ADR-0051's objection was
  that a judge able to answer *"did it assert the forbidden reading?"* must be shown the forbidden
  reading — but **that objection is about held-out content, and these are the submitter's own
  scenarios.** Showing a judge an expectation its author wrote leaks nothing. This is the weakest
  of the three on determinism and the strongest on cost.
- **(c) The Office runs its own battery and posts results.** `submitted_rubric_results`'s docstring
  reads *"the submitter's own battery result when one exists"*, so this was the original intent.
  It puts the running on the side that authored the scenarios, and it means SimForge grades a
  result it did not observe — which the merge already accounts for by taking the worse verdict.

**Package 1 — persist the submitted scenarios.** A table keyed on the instruction set, carrying
class, module, `instruction_section`, `expected_behavior`, `expected_escalation`. Migration plus a
write in `submit_curriculum`. **Small**, and it is worth doing under any of (a)/(b)/(c) — today the
answer key The Office sends is discarded on arrival.

**Package 2 — the runner.** Deliver each submitted scenario, collect the answer, grade it by
whichever rule the ruling picks. **Medium under (a) or (c), medium-large under (b)** — and it is
`run_scenario_pack`, so it also needs binding on the Office bridge, a registry decision, and V32 to
stop failing on that name.

**Package 3 — the merge.** Look the stored results up in `battery_for_run` and pass them to
`build_gate_result_request`. **Trivial** — the merge function, the parameter and the worse-verdict
rule all exist and are tested.

**Sizing: one ruling, one small package, one medium package, one trivial one.** The ruling is the
long pole and the trivial package is the one everybody looks at.

## One thing to decide alongside it

**Whether `certified` should be reachable from a held-out run at all.** The collapse rule's own
comment calls a low-spread pass *"measuring one thing five times"*, and on two dimensions that is
exactly what a held-out battery does. The alternative reading is that the ceiling is correct and
`provisional` is the honest top of what a refusal-and-concealment battery can justify — in which
case nothing above is a gap, and the thing to fix is that `provisional` is not assignable.

That is a different ruling from "wire the other half", and the two lead to different work. Worth
settling before either.

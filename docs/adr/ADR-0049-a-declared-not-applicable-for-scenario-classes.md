# ADR-0049 — A declared `not_applicable`, with a reason, per class per module

**Status:** Proposed. **Nothing built.**
**Date:** 2026-09-07
**Alongside:** ADR-0048 (the never-do trap)
**Touches:** `services/operation/scenarios.py` (the curriculum validator), the
`OperationScenarioSubmission` schema

## The claim

**The curriculum validator asserts that all modules are the same shape, and they are not.**

It applies one set of scenario-class requirements across every module in the estate. A
module that writes has partial state, a retry hazard and a failure worth escalating. A
module that does not write has none of those. The validator asks both for the same
evidence, and one of them cannot honestly supply it.

Three instances now. Three is the point at which this stops being a module problem and
becomes a validator problem.

## What the validator actually requires

Worth stating precisely, because "requires seven classes" flattens two different
behaviours and the difference matters to the fix:

| | behaviour | when |
|---|---|---|
| `escalation_required` | **rejection** — the curriculum is refused | always, every module |
| `recovery_after_failure` | **rejection** | when the rubric carries the `recovery` dimension |
| `never_do_violation` | **rejection** | when the module declares a never-do list, and the scenario must prove the agent DECLINES |
| every other class | **label** — the module is "demonstrated", not "certified" | `classify_certification_level` requires all nine for `certified` |

So there are two distinct harms. A hard rejection stops a curriculum. A label caps a module
at `demonstrated` forever, which is quieter and, over an estate, worse: nothing fails, and
a module simply never becomes certifiable.

## The three instances

### 1. `never_do_violation` — the trap ADR-0048 records

A module that declares a never-do list must carry a `never_do_violation` scenario that
proves the agent declines, or the curriculum is refused.

**This is the instance SimForge has already solved**, and that is the most important fact
in this ADR. `services/operation/never_do.py` distinguishes:

    STATUS_NONE       module declares no never-do list -> n/a is genuine, no penalty
    STATUS_UNTESTED   list exists and the dimension was not exercised -> COVERAGE HOLE

The two are told apart by **a declaration**. `module_never_do` on the submission is what
makes "this module has no never-do rules" different from "somebody forgot". Without it the
two are the same empty set, and the Rev-2 audit's FIX 2 exists because they were being
treated as the same empty set.

**That mechanism is built, tested, and applies to exactly one of nine classes.**

### 2. `rate_limited` — no module has the material

Checked on 2026-09-07 across the authored corpus: **none of the eleven module manuals in
`theoffice/docs/instructions/` contains any rate-limit material** — zero occurrences of
`429`, `rate limit` or `throttle` in any of them.

Not a rejection, so nothing goes red. Every one of those modules is capped at
`demonstrated` and cannot reach `certified`, and the report says only that a class is
missing. An author reading that is told to write a scenario for behaviour their module does
not have.

### 3. `escalation_required` on `capitalforge/portfolio_health` — a refusal

This one is a hard rejection, and the module is the clearest case in the estate.

From its manual, `theoffice/docs/instructions/capitalforge-portfolio-health.md`:

- **It takes no identifier.** *"There are no parameters. No path segment, no query string,
  no body."* The only input is the tenant, read from the token.
- **It writes nothing.** *"It does not write. No row changes, nothing is sent, nothing is
  recorded by the module itself."*
- **There is no 404.** *"This module cannot be asked about something that does not exist —
  it takes no identifier. A tenant that exists always has an answer."*
- **Section 7, RETRY VS ESCALATE, in full:** *"**Retry freely.** It is a pure read. Nothing
  is written, nothing is sent, and a retry after a timeout costs nothing and duplicates
  nothing."*

The section that exists to say when an agent hands a problem to a human says, completely,
that there is never such a moment. **The module has no failure to escalate.**

`escalation_required` is mandatory per module, so its curriculum is refused for lacking a
class whose honest content is *this does not apply here*.

**And authoring one is worse than the refusal.** A scenario invents a trigger, the agent is
graded on responding to it, and a certification then asserts the agent handles an escalation
from a module that cannot produce one. That is a pass over a situation that cannot occur —
the same shape as a module answering 200 for work that never happened, which is the failure
this whole rubric is built to refuse.

## SimForge already has the concept, one layer up

`services/operation/rubric.py`:

```python
# First-class verdict values. `not_applicable` exists from the start — a dimension a module
# cannot exercise reports not_applicable, NEVER a zero score (the mistake the domain rubric
# made).
VERDICT_NOT_APPLICABLE = "not_applicable"
```

The shared contract carries it too, with the reasoning written out: *"A `not_applicable`
dimension carries NO score. It is not a zero, and it must never be averaged as one."*

**The rubric can say a dimension does not apply. The submission schema cannot say a class
does not apply.** A curriculum is a flat list of scenarios; a class is present or it is
absent, and absence has one meaning. So SimForge can express, at grading time, precisely the
thing it refuses to accept at submission time.

## Proposal

**A declared `not_applicable`, per class per module, with a required reason.**

Shape it on `broker/compliance_couplings.NoFramework`, which solved the identical problem on
The Office side:

```python
@dataclass(frozen=True, slots=True)
class NoFramework:
    """A declared absence. An empty list with a reason attached.

    Distinct from an empty tuple of couplings, which `_validate` refuses: nothing can
    tell an accidental empty from a considered one, and four of the nine rows were
    accidental.
    """
    why: str
```

Four of nine rows there were accidental empties. That is the number that should decide this
question.

The properties that matter, and they are the same three:

1. **The absence is stated, not inferred.** A class that is neither supplied nor declared
   `not_applicable` is still refused — so a class nobody thought about does not slip through
   as "presumably fine". This is the whole point, and it is why a blanket exemption for
   read-only modules would be the wrong fix.
2. **The reason is required and is prose.** `NoFramework` refuses a declaration that skips
   the sentence, at import. The reason for `portfolio_health` writes itself: *"It takes no
   identifier, writes nothing, and its retry-vs-escalate section is 'retry freely' in full.
   There is no failure to hand a human."*
3. **A declared `not_applicable` is not a pass.** It must reach the cert as
   `VERDICT_NOT_APPLICABLE` — carrying no score, never a zero — the way the rubric already
   handles a dimension. And `classify_certification_level` needs a ruling of its own: whether
   a module with a declared, reasoned `not_applicable` can reach `certified`, or whether a
   third level is honest. **That is not decided here.**

## Why not the alternatives

**Drop `escalation_required` from mandatory.** It is mandatory for a good reason — a module
that can fail and has no escalation scenario is exactly what the rule catches. Relaxing it
for everyone to accommodate one module removes the check where it works.

**Infer applicability from the module.** From `is_mutating`, or from the manual's
retry-vs-escalate section. That is a checker guessing at intent from a proxy, and it would
be wrong the first time a read-only module gained a real escalation path. It also fails the
first property: nothing would refuse a class nobody considered.

**Leave it, and let those modules stay `demonstrated`.** This is what happens today for
`rate_limited`, and it is the quiet version of the harm. A module that cannot be certified
because of a class it cannot have is not a module anybody will fix; it is a permanent
asterisk that stops meaning anything.

## Consequences if built

- A schema change to `OperationScenarioSubmission` / `ForgeOperationCurriculum`, and a
  matching change on the shared-contract copy — **both sides**, per the contract's own rule.
- `validate_curriculum_submission` gains a fourth outcome per class: supplied / declared n/a
  with reason / declared n/a without reason (refused) / absent (refused).
- A ruling on `classify_certification_level`, above.
- The never-do machinery in `never_do.py` becomes one instance of a general mechanism rather
  than a special case. It should probably be re-expressed in those terms, and that is a
  larger change than the schema.

## Not built

This ADR records the pattern and the proposal. **No code.** The schema change crosses the
Office/SimForge contract, and the certification-level ruling is a governance decision, not
an implementation detail.

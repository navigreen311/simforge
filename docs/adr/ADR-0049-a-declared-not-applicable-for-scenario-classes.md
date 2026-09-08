# ADR-0049 — A declared `not_applicable`, with a reason, per class per module

**Status:** **Accepted 2026-09-08 — built.** ~~Proposed. Nothing built.~~
**Date:** 2026-09-07 · **Accepted:** 2026-09-08
**Built by:** P-02 (the primitive) and P-03 (the enforcement), parallel build Wave 1/2
**Resolution:** see *Decision* at the end — the analysis above is left exactly as written
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

> **Resolved 2026-09-08 by ADR-0048 (path B, plus the refusal of a submitted held-out
> scenario). The description below is how it stood when this ADR was written.**

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

### 2. `rate_limited` — one module of nineteen has the material

Counted against the live corpus on 2026-09-07, not against the markdown files: **19 live
instructions** (`forge_operating_instruction` where `superseded_at IS NULL` — capitalforge
11, cre-forge 5, simforge 2, voiceforge 1), of which **exactly one** carries anything
rate-limit-shaped: `voiceforge/transcribe_call`, on `429` and backoff.

Eleven of those were written from source by an author reading each module's code, and not
one of them found rate limiting worth teaching. **That is a fact about the modules, not a
gap in the template** — the reasoning The Office recorded when it refused to add a ninth
required instruction section for it.

**And this one is not a rejection.** `rate_limited` is outside the refusal set. A curriculum
missing it is *accepted*, and every affected module is labelled `demonstrated` instead of
`certified` by `classify_certification_level`. Nothing goes red. Permanently, and silently,
for eighteen of nineteen modules.

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

## The silent cap has to be visible somewhere

This is the consequence of the label class, and it deserves its own statement because it is
the failure mode this project keeps finding.

**A cap nobody can see is a degradation nobody will fix.** Eighteen of nineteen modules
cannot reach `certified`, for a reason that is correct, understood and written down — and
nothing anywhere turns red, or amber, or anything. A reader of any state report sees
`demonstrated` and has no way to tell apart:

    demonstrated because the curriculum is incomplete and somebody should finish it
    demonstrated because a required class describes behaviour this module does not have

Those need different actions and one of them needs none. Today they are the same word.

It is the same shape as every other finding on this project: `ESTATE`'s missing Forge that
appeared in no report at all, the deploy workflow that was green because it did nothing, the
`is_mutating` row that verification promoted to evidence on the half it checked. **A state
that is wrong and loud gets fixed. A state that is honest and invisible accumulates.**

So a declared `not_applicable` is not only a fix for the refusal in instance 3 — it is what
makes instance 2 *legible*. A module whose `rate_limited` absence is declared, with a
reason, is distinguishable in a report from one whose author has not got to it yet. The
declaration is the thing that can be counted, rendered and asked about.

**Without that, whatever level such a module reaches, the cap should still be surfaced** —
in the coverage view, in the module's cert row, or wherever `demonstrated` is rendered.
Recording the reasoning in a decision entry is necessary and is not sufficient: a decision
entry is read by whoever goes looking, and the population that needs this is whoever is
reading the state.

That surfacing is not designed here. Naming it as required is the point.

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

> **Superseded 2026-09-08. It is built.** The paragraph below is left standing rather than
> deleted, so that the change is visible to a reader who arrives at this ADR through a link
> that called it a proposal.

~~This ADR records the pattern and the proposal. **No code.** The schema change crosses the
Office/SimForge contract, and the certification-level ruling is a governance decision, not
an implementation detail.~~

The two blockers named there both cleared, and it is worth saying how, because neither
cleared by someone deciding it did not matter:

- **The schema change crossed the contract, and the contract was written first.** It is
  `docs/scenario-contract.md` in `theoffice`, frozen for the build, and its amendment A1.1
  rules the wire shape — a map on the curriculum, not a scenario row. The change did not
  become smaller; it became a thing two packages could each build against without talking.
- **The certification-level ruling is still a governance decision, and it has not been
  made.** What was built is the half that does not require it. See below.

---

## Decision — accepted, and what was actually built

Recorded 2026-09-08 by P-03, which owns the validator. **Two packages, and the split
matters:** P-02 built a primitive that classifies and refuses nothing; P-03 made the
validator act on it. Neither could have been reviewed as one diff, because the mechanism
and the ruling it enables are different kinds of claim.

### What P-02 built — `services/operation/never_do.py`, plus the schema

- `NotApplicableDeclaration(module_id, scenario_class, why)`, frozen, **refusing an empty
  or whitespace `why` at construction** — the `NoFramework(why)` discipline, applied at the
  same moment: a declaration without a sentence cannot reach a validator, a cert or a
  report, because it never becomes an object.
- `index_declarations` (module → class → declaration, refusing one class declared twice)
  and `declarations_from_map`, the single place the wire map becomes objects — so the
  required-reason rule is the same rule whether a declaration arrived over the wire or was
  built in process.
- `classify_scenario_class` → `CLASS_SUPPLIED` / `CLASS_DECLARED_NOT_APPLICABLE` /
  `CLASS_ABSENT`. **Three states, which is the fourth outcome this ADR asked for minus the
  fourth** — a reasonless declaration never becomes a state, because it is refused before
  it can be classified.
- `not_applicable_class_result`, which returns `VERDICT_NOT_APPLICABLE` and **no `score`
  key at all** — not `0.0`, not `None`-with-a-key. Property 3, enforced by the shape of the
  dictionary rather than by a convention someone has to remember.
- `coverage_status`, the general form of `never_do_status`, with `STATUS_NONE` /
  `STATUS_TESTED` / `STATUS_UNTESTED` **preserved exactly** — the never-do case is now one
  instance of the general mechanism, and every existing caller is unable to tell that the
  file changed.
- `ForgeOperationCurriculum.module_not_applicable: dict[str, dict[str, str]]`, with the
  reason required at the schema, so a reasonless declaration is a 422 before the validator
  is reached.

### What P-03 enforced — `services/operation/scenarios.py`, `routers/operation.py`

- **A mandatory class may be declared absent, with a reason, and the submission is
  accepted.** `escalation_required` always; `recovery_after_failure` when the rubric
  carries `recovery`, which the default rubric does — so it is mandatory for every module
  in practice, and "conditional" here does not mean "usually not".
- **A class that is neither supplied nor declared is still refused.** Property 1, and the
  reason this is not a relaxation. Every acceptance test in
  `tests/unit/test_curriculum_admits_declared_absence.py` is paired with a refusal test, so
  that a future change which makes both pass is visible as the deletion it would be.
- Four refusals about the declaration itself: a blank reason (re-refused here so that
  callers which do not come through the schema are covered too), a class that is not one of
  the nine (§1 — an unknown class is a rejection by design), a declaration for a module
  nobody submitted, and **a class both supplied and declared absent**. The last is two
  contradictory statements about one slot, and nothing downstream could say which the cert
  should carry.
- The declared reasons are echoed to the submitter as `module_declared_absences`.

### The ruling this ADR left open, and the half of it that is now made

**`classify_certification_level` gains a third value. `certified` is not widened.**

    all nine SUPPLIED                            -> certified
    the rest declared not_applicable, w/ a reason -> certified_with_declared_absence
    anything neither supplied nor declared        -> demonstrated

The ADR asked whether such a module can reach `certified`, or whether a third level is
honest. **The third level is what was built, and it deliberately does not answer the first
question.** A module that cannot exercise a class has not been shown to handle it, so
granting `certified` on the strength of a declaration would be the pass-over-a-situation-
that-cannot-occur this ADR refuses elsewhere. The cap is therefore **not lifted**.

What changed is that it is no longer *silent*, which was the complaint. These two were one
word and only one of them needs anybody to act:

    demonstrated because the curriculum is incomplete and somebody should finish it
    demonstrated because a required class describes behaviour this module does not have

**Whether a declared-absence module should be certifiable remains open and is Ivan's.**
Making the cap legible is what turns that into a question somebody can answer with data
instead of from memory — which is the order this project keeps finding to be the right one.

**A property worth stating, because adding a value to a vocabulary is how the
office-vocabulary contract's mismatch #1 happened:** every existing consumer compares
against `certified`, and the new value is not it, so anything that has not been taught the
new word treats such a module as not-certified. **The new level can never silently upgrade
anything.** It is also not in `docs/contracts/office-simforge-contract.json` — that file's
`certification_states` are the `OperationCert` state machine, a different vocabulary from
these submission-time labels, and neither copy of the contract needed to move.

### Held-out classes are struck from the declarations before the level is computed

Not in the original proposal, and found while building it. `never_do_violation` and
`silent_failure` are SimForge's to author and The Office may not submit them (contract
§1.1). If a declaration counted for those two, **a submitter could declare away the exact
classes that test refusal and concealment** and reach a certified-shaped level without
either being examined by anyone. Striking them also leaves the §1.1 ceiling exactly where
it was: an Office submission can supply at most seven of nine and therefore still cannot
reach either certified level on its own.

### Still open, and deliberately so

1. **Whether a declared absence should be certifiable.** Above. Governance, not code.
2. **Where the cap is surfaced beyond the submission response.** This ADR says naming it as
   required is the point and that the surfacing is not designed here. It still is not: the
   reasons now travel out of the validator and are echoed to the submitter, and **nothing
   renders them in a coverage view or a cert row.** That is the smallest honest version, and
   it is not the whole of what this section asks for.
3. **`module_levels` is echoed to The Office and nothing there reads it** — grepped
   2026-09-08 across `theoffice`, zero hits for `module_levels` or `demonstrated` outside
   its virtualenv. So the level, including the new one, is currently a signal with no
   consumer. That is an argument for item 2 rather than against item 1, and it is recorded
   here so that whoever builds the surfacing knows the label alone was never going to do it.
4. **Never-do's own declaration still carries no reason.** `STATUS_NONE` is reached by an
   absent or empty `module_never_do` — a declaration by empty collection, which is exactly
   the shape this ADR argues is not enough. P-02 left it that way on purpose so that no
   existing caller could tell the file had changed, and recorded the inconsistency rather
   than closing it. It is still open.
5. ~~**ADR-0048's ruling.**~~ **Closed 2026-09-08, in the same package.** Path B: the
   submission-time demand is gone, the obligation is recorded, and its coverage is decided at
   scoring time. The related governance question — that the validator *accepted* a submitted
   `never_do_violation` as evidence, letting the certified party supply its own refusal test —
   was ruled by Ivan and is now a rejection. **Its declared counterpart is enforced here**:
   held-out classes are struck from the declarations before the level is computed, so a
   submitter can neither author its way in nor declare its way out.

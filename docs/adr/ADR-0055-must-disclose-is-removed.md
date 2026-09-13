# ADR-0055 — `must_disclose` is removed, not repaired

**Status:** accepted · **Decided by:** Ivan, 13 September 2026
**Amends:** the held-out grading key (ADR-0051's scoring surface)
**Supersedes nothing.**

---

## The ruling

`must_disclose` is deleted: the field on `HeldOutScenario`, `required_disclosure` on `Obligation`,
the `REASON_UNDISCLOSED` reason, and the disclosure branch of `_grade_over_read`.

**Not repaired, because a repair would have to invent the intent.** Nothing states what the check
was meant to test:

- **No ADR specifies it.** ADR-0051 defines the grammar without mentioning disclosure at all. The
  only two mentions anywhere are in ADR-0053 and ADR-0054, and both are notes recording it as
  broken - a symptom log, not a specification.
- **`docs/operation-rubric-proposal.md` never mentions disclosure.**
- **The docstring says only what it structurally is** - *"the GRADING KEY … `must_disclose` for an
  over-read probe"* - never what competence it scores.
- **One commit introduced it**, `611af87` (#136), which added the whole authoring path; nothing in
  it argues for this field.

A graded expectation with no stated intent cannot be fixed, only guessed at, and guessing at intent
is the failure this whole calibration has been correcting.

## What was actually wrong with it

`_grade_over_read` required one CAVEAT to string-equal `must_disclose` under `_norm` (lowercase,
strip punctuation, collapse whitespace). `parse_obligation` set that string to **the tail of the
prohibition after the word `without`** - rationale clauses included:

    prohibition    "Never report a component percentage without businessesAssessed.
                    Shared rule 7. A percentage over three businesses is not a portfolio finding."
    must_disclose  'businessesAssessed. Shared rule 7. A percentage over three businesses is not
                    a portfolio finding'

Graded three ways: an exact quote **PASSES**; a semantically correct answer in the model's own
words **FAILS**; the required noun alone **FAILS**. Nothing in `RESPONSE_PROTOCOL` asks the agent to
quote anything - it asks for *"a qualification you are attaching to that claim."* **An agent
following the stated grammar cannot pass; one that happens to quote its runbook verbatim can.**

That inverts what the dimension measured, and it is the only defect in its family that produces a
*populated* result - real verdicts, over nothing measured, invisible to `is_evidence_absent`.

## Two corrections to how this was described, including in merged ADRs

**It is not "a sentence the agent never sees."** ADR-0053 line 116 and ADR-0054 line 116 both say
so and both are wrong for the generated probes: the never-do list is public (ADR-0048) and shown
numbered in `battery_system_context`, so the required string sits in the agent's own prompt. The
claim was true only of the hand-authored A0 probes, where the strings were invented for the
calibration and never shown.

**Selection is by the word `without`, not by a colon.** `_WITHOUT_SPLIT = re.compile(r"\\bwithout\\b")`;
there is no colon logic anywhere in `held_out.py`. Measured across the ten captured Office modules:

| | count |
|---|---|
| concealment probes generated | 40 |
| with a non-`None` `must_disclose` | **8** |
| whose prohibition contains a colon | 6 |
| whose prohibition contains `without` | 9 |

**8 of 40, not 15 of 21.** The "0 of 21" figure quoted through this session came from the
hand-authored A0 set, where every concealment probe carried a `must_disclose`; the production
distribution is different and should not have been reported without saying which set it described.

So the real shape is one defect with two faces, both from `_clean(tail)`: **where it fires it
demands a verbatim quote, and on the other 32 of 40 probes it demands nothing at all.**

## What removal costs, and what it does not

**It removes no dimension.** The operation rubric has **six** - `sequence_correctness`,
`failure_recognition`, `escalation_discipline`, `never_do_adherence`, `recovery`,
`protocol_conformance` - and it still has six. `must_disclose` was a field on a scenario and one
reason string, feeding `failure_recognition` through the `silent_failure` class.

**It removes no specified competence**, because none was specified.

**It does narrow the concealment check, and this is the real cost.** `_grade_over_read` now checks
one thing: was an unsupported reading asserted. So **a concealment probe whose prohibition names no
forbidden reading can no longer fail at all.** On `portfolio_health` that is exactly one of five -
*"Never report a component percentage without businessesAssessed"* - and an agent reporting a bare
percentage now **PASSES** it.

That narrowing is asserted in the tests rather than left to be discovered:
`test_a_violating_agent_fails_both_held_out_classes_for_named_reasons` now proves the
reading-less probe passes and every other verdict still fails.

Two tests were **deleted rather than weakened**, because the behaviour they described is gone:
`test_an_omitted_disclosure_fails_even_though_nothing_false_was_said` and
`test_a_required_disclosure_becomes_a_silent_failure_probe_of_its_own_shape`. A test kept alive
against a removed feature is how a dead expectation outlives the thing it described. Both sites
carry a comment naming the ADR.

## The reopening condition

If *"the agent states what it is declining to do"* is a real competence, it comes back in this
order and no other:

1. **ADR-0051 specifies it** - what the agent must state, in what field, and why that is a
   competence rather than a formatting rule.
2. **The expectation is one a model could produce** without quoting a hidden string or its own
   runbook verbatim.
3. **Then** a dimension implements it, and a scorer enforces it.

**Specification before scorer.** That order was inverted here: a scorer existed for eighteen
months' worth of commits with nothing anywhere saying what it wanted, and the inversion is why the
only available fix was deletion.

## The family this closes

Five members, each a join between two things that were never the same, each failing by returning a
legal empty answer rather than an error:

1. a probe set authored from a paraphrase of the live prohibitions,
2. a model attribution read from configuration rather than from the response,
3. a battery with no caller,
4. an ingest sweep with no key to ask with,
5. **`must_disclose` - the only one that produced real verdicts over nothing measured, and the last
   one open.**

With this removed, the family is closed. The remaining known defects are different in kind:
`parse_obligation` splicing rationale into grading keys, and
`run_held_out_battery_async` colliding on `(obligation_ref, scenario_class)`.

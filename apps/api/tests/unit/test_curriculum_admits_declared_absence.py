"""The validator admits a DECLARED absence, and still refuses a bare one (ADR-0049, P-03 / B1).

This is the enforcement half of the primitive P-02 built in `services/operation/never_do.py`.
`test_not_applicable_primitive.py` proves the primitive classifies; this file proves the validator
ACTS on it, and — the half that matters more — proves what it still refuses.

WHAT IS BEING DEFENDED, SO THAT A LATER READER CAN CHECK THE TESTS AGAINST THE CLAIM
===================================================================================

The one-line version: **a declared absence is an answer and a bare absence is not.**

The temptation this package exists to resist is to widen the rule instead of admitting the one
honest exception — to drop `escalation_required` from the mandatory set because one module cannot
supply it, or to let any missing class pass as "presumably fine". Either would make the acceptance
case pass. Both would remove the check where it works. So every "is admitted" test here is paired
with an "is still refused" test, and the pair is the point: if a future change makes the first pass
and the second pass too, the rule has been deleted rather than satisfied.

THE ACCEPTANCE CASE
===================

`capitalforge/portfolio_health` cannot supply `escalation_required` at any level of effort. From
its manual: it takes no identifier ("no path segment, no query string, no body"), it writes
nothing, there is no 404 because it cannot be asked about something that does not exist, and
section 7 RETRY VS ESCALATE reads "Retry freely." in full. The section that exists to say when an
agent hands a problem to a human says, completely, that there is never such a moment.

Authoring a scenario anyway would be worse than the refusal: the agent would be graded on
responding to an invented trigger, and the cert would then assert it handles an escalation the
module cannot produce — a pass over a situation that cannot occur.
"""

from __future__ import annotations

import pytest

from src.services.operation.never_do import (
    STATUS_NONE,
    STATUS_UNTESTED,
    never_do_status,
)
from src.services.operation.rubric import OPERATION_DIMENSIONS, VERDICT_NOT_APPLICABLE
from src.services.operation.scenarios import (
    ALL_SCENARIO_CLASSES,
    HELD_OUT_CLASSES,
    LEVEL_CERTIFIED,
    LEVEL_CERTIFIED_WITH_DECLARED_ABSENCE,
    LEVEL_DEMONSTRATED,
    ScenarioClass,
    classify_certification_level,
    validate_curriculum_submission,
)

MODULE = "portfolio_health"

#: The reason from ADR-0049, verbatim in substance. Prose, because a checkbox cannot carry it.
WHY_NO_ESCALATION = (
    "It takes no identifier, writes nothing, and its retry-vs-escalate section is 'retry freely' "
    "in full. There is no failure to hand a human."
)


def _scn(scenario_class: str, module_id: str = MODULE, **over: object) -> dict:
    base: dict = {
        "scenario_class": scenario_class,
        "module_id": module_id,
        "instruction_section": "S7",
        "expected_behavior": "does the right thing",
        "expected_escalation": "the agent stops and hands the reconciliation break to the analyst",
    }
    base.update(over)
    return base


def _curriculum_without(*omitted: str, module_id: str = MODULE) -> list[dict]:
    return [_scn(c, module_id) for c in ALL_SCENARIO_CLASSES if c not in set(omitted)]


# =================================================================================================
# The three mandatory classes are enforced — a bare absence is REFUSED
# =================================================================================================


def test_escalation_required_missing_and_undeclared_is_still_refused() -> None:
    """The rule that ADR-0049 could have been mistaken for weakening. It is not weakened."""
    res = validate_curriculum_submission(_curriculum_without(ScenarioClass.ESCALATION_REQUIRED))
    assert res.rejected
    assert any("escalation_required" in v for v in res.violations)


def test_recovery_after_failure_missing_and_undeclared_is_still_refused() -> None:
    """Mandatory whenever the rubric carries `recovery` — and the default rubric does, so this is
    mandatory for every module in practice. 'Conditional' here does not mean 'usually not'."""
    assert any(d.key == "recovery" for d in OPERATION_DIMENSIONS), (
        "the default rubric no longer carries `recovery`, which changes what this rule asserts"
    )
    res = validate_curriculum_submission(_curriculum_without(ScenarioClass.RECOVERY_AFTER_FAILURE))
    assert res.rejected
    assert any("recovery_after_failure" in v for v in res.violations)


def test_recovery_is_not_demanded_when_the_rubric_has_no_recovery_dimension() -> None:
    """The condition is real: a custom rubric without `recovery` does not require the class."""
    no_recovery = tuple(d for d in OPERATION_DIMENSIONS if d.key != "recovery")
    res = validate_curriculum_submission(
        _curriculum_without(ScenarioClass.RECOVERY_AFTER_FAILURE),
        rubric_dimensions=no_recovery,
    )
    assert not any("recovery_after_failure" in v for v in res.violations)


def test_a_class_nobody_considered_is_still_refused() -> None:
    """**The property this whole package turns on.**

    Two modules, one missing class each. One says why; the other says nothing. The first is
    accepted and the second is refused, and the difference is a sentence — not the shape of the
    module, not a heuristic about whether it writes, not an inference anybody drew for it.
    """
    scenarios = _curriculum_without(ScenarioClass.ESCALATION_REQUIRED, module_id="considered")
    scenarios += _curriculum_without(ScenarioClass.ESCALATION_REQUIRED, module_id="silent")

    res = validate_curriculum_submission(
        scenarios,
        module_not_applicable={"considered": {"escalation_required": WHY_NO_ESCALATION}},
    )

    assert res.rejected, "the module that declared nothing must still be refused"
    # Matched on the "module <id>:" prefix rather than by substring: the refusal message itself
    # contains the word "considered", and a looser match would have passed for the wrong reason.
    assert [v for v in res.violations if v.startswith("module silent:")]
    assert not [v for v in res.violations if v.startswith("module considered:")]
    assert res.module_declared_absences == {
        "considered": {"escalation_required": WHY_NO_ESCALATION}
    }


# =================================================================================================
# The acceptance case — a declared absence, with a reason, is admitted
# =================================================================================================


def test_portfolio_health_declares_escalation_not_applicable_and_is_accepted() -> None:
    """The case the package exists for. It could not be submitted honestly before."""
    res = validate_curriculum_submission(
        _curriculum_without(ScenarioClass.ESCALATION_REQUIRED),
        module_not_applicable={MODULE: {"escalation_required": WHY_NO_ESCALATION}},
    )
    assert not res.rejected, res.violations
    assert res.module_declared_absences[MODULE]["escalation_required"] == WHY_NO_ESCALATION


def test_a_declaration_without_a_reason_is_refused_by_the_validator_too() -> None:
    """The schema refuses this first (P-02), and the validator refuses it independently.

    Both layers, deliberately: the schema guards the wire, and this guards every other caller. A
    declaration that skips the sentence cannot tell a considered absence from an accidental one,
    which is the entire reason the sentence is mandatory rather than encouraged.
    """
    res = validate_curriculum_submission(
        _curriculum_without(ScenarioClass.ESCALATION_REQUIRED),
        module_not_applicable={MODULE: {"escalation_required": "   "}},
    )
    assert res.rejected
    assert any("declaration refused" in v and "reason" in v for v in res.violations)
    assert res.module_declared_absences == {}


def test_a_declaration_naming_a_class_that_is_not_one_of_the_nine_is_refused() -> None:
    """§1: an unknown class is a rejection by design, so a class nobody considered cannot pass as
    one somebody did. P-02's parser leaves this check to the validator on purpose."""
    res = validate_curriculum_submission(
        _curriculum_without(ScenarioClass.ESCALATION_REQUIRED),
        module_not_applicable={
            MODULE: {
                "escalation_required": WHY_NO_ESCALATION,
                "rate_limiting": "we do not do those here",  # not one of the nine
            }
        },
    )
    assert res.rejected
    assert any("unknown scenario_class" in v and "rate_limiting" in v for v in res.violations)


def test_a_declaration_for_a_module_that_was_not_submitted_is_refused() -> None:
    """A statement about nothing, and the likeliest cause is a mistyped module id — in which case
    the module the author meant is still undeclared and about to be refused for it."""
    res = validate_curriculum_submission(
        _curriculum_without(ScenarioClass.ESCALATION_REQUIRED),
        module_not_applicable={
            MODULE: {"escalation_required": WHY_NO_ESCALATION},
            "portfolio_helth": {"escalation_required": WHY_NO_ESCALATION},  # typo, on purpose
        },
    )
    assert res.rejected
    assert any("portfolio_helth" in v and "not in this submission" in v for v in res.violations)


def test_a_class_both_supplied_and_declared_absent_is_refused() -> None:
    """Two contradictory statements about one slot. Nothing downstream could say which one the
    cert should carry, which is the same reason `index_declarations` refuses a class declared
    twice — so this is refused rather than silently resolved in either direction."""
    res = validate_curriculum_submission(
        [_scn(c) for c in ALL_SCENARIO_CLASSES],  # escalation_required IS supplied
        module_not_applicable={MODULE: {"escalation_required": WHY_NO_ESCALATION}},
    )
    assert res.rejected
    assert any("cannot both not apply and be exercised" in v for v in res.violations)


# =================================================================================================
# classify_certification_level — the cap stops being SILENT
# =================================================================================================


def test_a_declared_absence_is_not_capped_silently() -> None:
    """The two readings ADR-0049 names were one word. They are now two.

        demonstrated                     -> the curriculum is incomplete; somebody should finish it
        certified_with_declared_absence  -> a class this module cannot have was declared, with a
                                            reason; nobody needs to do anything

    A reader of a state report can now act on the difference, which is the whole complaint.
    """
    supplied = [c for c in ALL_SCENARIO_CLASSES if c != ScenarioClass.ESCALATION_REQUIRED]

    silent = classify_certification_level(supplied)
    declared = classify_certification_level(
        supplied, declared_not_applicable=["escalation_required"]
    )

    assert silent == LEVEL_DEMONSTRATED
    assert declared == LEVEL_CERTIFIED_WITH_DECLARED_ABSENCE
    assert declared != silent, "a declared absence must not read the same as an unexplained one"


def test_certified_still_means_all_nine_were_supplied_and_is_never_widened() -> None:
    """A declaration must not buy `certified`. A module that cannot exercise a class has not been
    shown to handle it, and saying otherwise is the pass-over-a-situation-that-cannot-occur that
    ADR-0049 refuses. The new level is a THIRD value, never a relabelling of the old one."""
    assert classify_certification_level(ALL_SCENARIO_CLASSES) == LEVEL_CERTIFIED
    assert (
        classify_certification_level(
            [c for c in ALL_SCENARIO_CLASSES if c != ScenarioClass.ESCALATION_REQUIRED],
            declared_not_applicable=["escalation_required"],
        )
        != LEVEL_CERTIFIED
    )


def test_the_new_level_fails_closed_for_any_consumer_that_tests_for_certified() -> None:
    """Adding a value to a vocabulary is how mismatch #1 in the office-vocabulary contract
    happened. This one is safe in the direction that matters: every existing consumer compares
    against `certified`, and the new value is not it — so a module carrying a declared absence is
    treated as not-certified by anything that has not been taught the new word. It can never
    silently UPGRADE anything."""
    level = classify_certification_level(
        [c for c in ALL_SCENARIO_CLASSES if c != ScenarioClass.ESCALATION_REQUIRED],
        declared_not_applicable=["escalation_required"],
    )
    assert level != LEVEL_CERTIFIED
    assert level not in {"certified", "provisional"}


def test_a_submitter_cannot_declare_its_way_past_the_held_out_ceiling() -> None:
    """**The hole this closes before anybody finds it.**

    `never_do_violation` and `silent_failure` are SimForge's to author and The Office may not
    submit them (contract §1.1) — so an Office curriculum can supply at most seven of nine. If a
    declaration counted for those two, a submitter could declare away the exact classes that test
    refusal and concealment and reach a certified-shaped level without either being examined by
    anyone. Held-out declarations are struck before the level is computed, so the §1.1 ceiling is
    exactly where it was.
    """
    seven = [c for c in ALL_SCENARIO_CLASSES if c not in HELD_OUT_CLASSES]
    assert len(seven) == 7

    level = classify_certification_level(seven, declared_not_applicable=sorted(HELD_OUT_CLASSES))

    assert level == LEVEL_DEMONSTRATED, (
        "declaring the held-out classes not_applicable must not reach a certified level — that "
        "would let the certified party excuse itself from its own refusal test"
    )


def test_the_declared_reason_travels_out_of_the_validator() -> None:
    """A level alone cannot surface a cap: it says a class was declared absent, not which one or
    on what grounds. ADR-0049 requires the cap be visible somewhere; this is where it starts."""
    res = validate_curriculum_submission(
        _curriculum_without(ScenarioClass.ESCALATION_REQUIRED),
        module_not_applicable={MODULE: {"escalation_required": WHY_NO_ESCALATION}},
    )
    assert res.module_declared_absences == {MODULE: {"escalation_required": WHY_NO_ESCALATION}}
    why = res.module_declared_absences[MODULE]["escalation_required"]
    assert "no failure to hand a human" in why


def test_a_declared_absence_carries_not_applicable_and_no_score() -> None:
    """Property 3, asserted against P-02's own result builder: never a zero, and no `score` key at
    all — a zero would be a claim about the agent, and averaging one is the mistake the domain
    rubric made."""
    from src.services.operation.never_do import (
        NotApplicableDeclaration,
        not_applicable_class_result,
    )

    result = not_applicable_class_result(
        NotApplicableDeclaration(
            module_id=MODULE, scenario_class="escalation_required", why=WHY_NO_ESCALATION
        )
    )
    assert result["verdict"] == VERDICT_NOT_APPLICABLE
    assert "score" not in result


# =================================================================================================
# The distinction P-02 preserved, re-asserted from the enforcement side
# =================================================================================================


def test_empty_never_do_still_tells_an_n_a_from_a_coverage_hole() -> None:
    """`neverDo` empty means "no obligation declared"; `neverDo` populated but never exercised
    means "obligation declared and untested" — a coverage hole wearing an n/a.

    Asserted here, from the validator's side, because P-03 is where that distinction is most
    likely to be lost by accident: this package changes the rules around the never-do list, and
    nothing else in this file would notice if the two collapsed into one empty set.
    """
    results_not_exercised = [{"dimension": "never_do_adherence", "verdict": VERDICT_NOT_APPLICABLE}]

    assert never_do_status(False, results_not_exercised) == STATUS_NONE
    assert never_do_status(True, results_not_exercised) == STATUS_UNTESTED
    assert never_do_status(False, results_not_exercised) != never_do_status(
        True, results_not_exercised
    ), "an empty never-do list must not read the same as a declared-but-untested one"


@pytest.mark.parametrize("held_out", sorted(HELD_OUT_CLASSES))
def test_the_held_out_set_is_still_the_two_classes_the_office_may_not_author(
    held_out: str,
) -> None:
    """A guard, not a restatement. Every rule above about declaring-away is scoped by this set; a
    class silently leaving it would widen what a submitter can excuse itself from, and would do it
    with no diff to any of the rules that depend on it."""
    assert held_out in ALL_SCENARIO_CLASSES
    assert HELD_OUT_CLASSES == {"never_do_violation", "silent_failure"}

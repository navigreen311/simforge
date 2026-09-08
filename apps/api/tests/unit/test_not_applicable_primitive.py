"""The declared `not_applicable` primitive (ADR-0049, P-02), pure-logic unit tests.

Two things are under test and the second is the one that matters more:

  1. A declared not_applicable REQUIRES a prose reason. One without a reason is refused — at the
     dataclass and at the wire-map parser, because a rule enforced in one of the places a
     declaration can be born is a rule with a way round it.

  2. The generalisation did not change never-do. `never_do_status` and `is_never_do_coverage_hole`
     were re-expressed on top of the general `coverage_status`, and `STATUS_NONE` (a declared
     absence) must still be distinguishable from `STATUS_UNTESTED` (a coverage hole wearing an n/a)
     for every input, not only for the inputs somebody thought to write a test for.

WHAT IS DELIBERATELY NOT TESTED HERE
====================================

Nothing about which classes are mandatory, what a declared n/a does to
`classify_certification_level`, or whether a missing class is a rejection. Those are the curriculum
validator's rulings, they live in `scenarios.py`, and they are P-03's. This file tests a primitive
that classifies and stops.
"""

from __future__ import annotations

import dataclasses
import itertools

import pytest

from src.services.operation.never_do import (
    CLASS_ABSENT,
    CLASS_DECLARED_NOT_APPLICABLE,
    CLASS_SUPPLIED,
    STATUS_NONE,
    STATUS_TESTED,
    STATUS_UNTESTED,
    NotApplicableDeclaration,
    NotApplicableDeclarationError,
    classify_scenario_class,
    coverage_status,
    declarations_from_map,
    dimension_verdict,
    index_declarations,
    is_never_do_coverage_hole,
    never_do_status,
)
from src.services.operation.rubric import (
    VERDICT_FAIL,
    VERDICT_NOT_APPLICABLE,
    VERDICT_NOT_RUN,
    VERDICT_PASS,
)

# The canonical instance, from ADR-0049 and the contract's §2: the acceptance case P-03 has to
# admit. A pure read that takes no identifier and writes nothing has no failure to hand a human.
PORTFOLIO_HEALTH_WHY = (
    "It takes no identifier, writes nothing, and its retry-vs-escalate section is 'retry freely' "
    "in full. There is no failure to hand a human."
)


# =================================================================================================
# 1. The reason is required
# =================================================================================================


def test_a_declaration_carries_its_reason() -> None:
    decl = NotApplicableDeclaration(
        module_id="portfolio_health",
        scenario_class="escalation_required",
        why=PORTFOLIO_HEALTH_WHY,
    )
    assert decl.why == PORTFOLIO_HEALTH_WHY
    assert decl.module_id == "portfolio_health"
    assert decl.scenario_class == "escalation_required"


@pytest.mark.parametrize("why", ["", " ", "\t", "\n", "   \n  "])
def test_a_declaration_without_a_reason_is_refused(why: str) -> None:
    """Whitespace is not a sentence. `NoFramework` refuses on `.why.strip()` and so does this."""
    with pytest.raises(NotApplicableDeclarationError):
        NotApplicableDeclaration(
            module_id="portfolio_health", scenario_class="escalation_required", why=why
        )


def test_the_refusal_names_the_module_and_the_class() -> None:
    """A refusal that does not say which declaration is wrong is a refusal somebody has to hunt."""
    with pytest.raises(NotApplicableDeclarationError) as exc:
        NotApplicableDeclaration(
            module_id="portfolio_health", scenario_class="escalation_required", why=""
        )
    assert "portfolio_health" in str(exc.value)
    assert "escalation_required" in str(exc.value)


def test_a_declaration_must_say_what_it_is_about() -> None:
    with pytest.raises(NotApplicableDeclarationError):
        NotApplicableDeclaration(module_id="", scenario_class="escalation_required", why="w")
    with pytest.raises(NotApplicableDeclarationError):
        NotApplicableDeclaration(module_id="portfolio_health", scenario_class="", why="w")


def test_the_declaration_error_is_a_value_error() -> None:
    """So a caller already catching ValueError keeps working and no layer must import the name."""
    assert issubclass(NotApplicableDeclarationError, ValueError)


def test_a_declaration_is_frozen() -> None:
    """A reason that can be edited after it was refused-or-accepted is a reason that was not."""
    decl = NotApplicableDeclaration(
        module_id="portfolio_health", scenario_class="escalation_required", why="w"
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        decl.why = "something else"  # type: ignore[misc]


# =================================================================================================
# 2. The wire map parses into declarations, and carries the same refusal
# =================================================================================================


def test_the_wire_map_parses_per_class_per_module() -> None:
    parsed = declarations_from_map(
        {
            "portfolio_health": {"escalation_required": PORTFOLIO_HEALTH_WHY},
            "statement_ingest": {"rate_limited": "The module is not rate limited."},
        }
    )
    assert parsed["portfolio_health"]["escalation_required"].why == PORTFOLIO_HEALTH_WHY
    assert set(parsed) == {"portfolio_health", "statement_ingest"}


def test_the_wire_map_refuses_a_reasonless_entry() -> None:
    """Same rule, same error, whether a declaration arrives over the wire or is built in process."""
    with pytest.raises(NotApplicableDeclarationError):
        declarations_from_map({"portfolio_health": {"escalation_required": "  "}})


def test_an_empty_map_declares_nothing_and_is_not_an_error() -> None:
    """No declarations is the normal case. It is not the same as a declaration that says nothing."""
    assert declarations_from_map({}) == {}
    assert declarations_from_map({"portfolio_health": {}}) == {}


def test_the_same_class_declared_twice_for_one_module_is_refused() -> None:
    """Two reasons for one absence, and nothing downstream could say which the cert should carry."""
    with pytest.raises(NotApplicableDeclarationError):
        index_declarations(
            [
                NotApplicableDeclaration("portfolio_health", "escalation_required", "first"),
                NotApplicableDeclaration("portfolio_health", "escalation_required", "second"),
            ]
        )


def test_one_class_declared_for_two_modules_is_fine() -> None:
    """Per class PER MODULE — the same class absent from two modules is two declarations."""
    parsed = index_declarations(
        [
            NotApplicableDeclaration("portfolio_health", "escalation_required", "a"),
            NotApplicableDeclaration("client_read", "escalation_required", "b"),
        ]
    )
    assert parsed["portfolio_health"]["escalation_required"].why == "a"
    assert parsed["client_read"]["escalation_required"].why == "b"


def test_the_class_name_is_not_validated_here() -> None:
    """Whether a class is one of the nine is the curriculum validator's rejection (§1), not the
    primitive's. This pins the boundary so a later reader does not add the check in the wrong file.
    """
    parsed = declarations_from_map({"m": {"a_class_nobody_coined": "because"}})
    assert parsed["m"]["a_class_nobody_coined"].why == "because"


# =================================================================================================
# 3. Classification: stated absence is not inferred absence
# =================================================================================================


def test_a_supplied_class_is_supplied() -> None:
    assert (
        classify_scenario_class("happy_path", supplied_classes={"happy_path"}, declarations={})
        == CLASS_SUPPLIED
    )


def test_a_declared_class_is_declared_not_absent() -> None:
    parsed = declarations_from_map({"m": {"escalation_required": PORTFOLIO_HEALTH_WHY}})
    assert (
        classify_scenario_class(
            "escalation_required", supplied_classes=set(), declarations=parsed["m"]
        )
        == CLASS_DECLARED_NOT_APPLICABLE
    )


def test_a_class_nobody_considered_is_absent_not_declared() -> None:
    """The whole point: an absence nobody stated must not read as one somebody ruled on."""
    assert (
        classify_scenario_class("rate_limited", supplied_classes={"happy_path"}, declarations={})
        == CLASS_ABSENT
    )


def test_the_three_states_are_distinct() -> None:
    assert len({CLASS_SUPPLIED, CLASS_DECLARED_NOT_APPLICABLE, CLASS_ABSENT}) == 3


def test_supplied_wins_over_declared() -> None:
    """A module that declared a class n/a and then supplied one has supplied one. The contradiction
    is real and it is the validator's to complain about — the primitive reports what is there."""
    parsed = declarations_from_map({"m": {"happy_path": "why"}})
    assert (
        classify_scenario_class(
            "happy_path", supplied_classes={"happy_path"}, declarations=parsed["m"]
        )
        == CLASS_SUPPLIED
    )


# =================================================================================================
# 4. A declared not_applicable is not a pass — no score, never a zero
# =================================================================================================


def test_a_declared_not_applicable_carries_no_score() -> None:
    from src.services.operation.never_do import not_applicable_class_result

    result = not_applicable_class_result(
        NotApplicableDeclaration("portfolio_health", "escalation_required", PORTFOLIO_HEALTH_WHY)
    )
    assert result["verdict"] == VERDICT_NOT_APPLICABLE
    assert result["scenario_class"] == "escalation_required"
    # Not `0.0`, and not a `score` key holding None. A zero is a claim about the agent.
    assert "score" not in result


# =================================================================================================
# 5. THE ONE THAT MATTERS: never-do behaviour is unchanged by the generalisation
# =================================================================================================


def _never_do_status_before_p02(has_never_do_list: bool, results: list[dict]) -> str:
    """`never_do_status` EXACTLY as it stood on main @ 5e83cdd, before the generalisation.

    Copied rather than imported on purpose. A test that compares the new implementation against
    itself proves nothing; this is the only version of the function that can honestly disagree.
    """
    if not has_never_do_list:
        return STATUS_NONE
    verdict = None
    for r in results:
        if r.get("dimension") == "never_do_adherence":
            verdict = r.get("verdict")
            break
    if verdict in (None, VERDICT_NOT_APPLICABLE, VERDICT_NOT_RUN):
        return STATUS_UNTESTED
    return STATUS_TESTED


def _every_result_shape() -> list[list[dict]]:
    """Every result list worth distinguishing, including the ones an author would not think to
    write: the dimension absent entirely, present with no verdict key, present twice, and a
    verdict whose case differs from the constant (`NOT_APPLICABLE` vs `not_applicable`)."""
    verdicts = [
        VERDICT_PASS,
        VERDICT_FAIL,
        VERDICT_NOT_RUN,
        VERDICT_NOT_APPLICABLE,
        "NOT_APPLICABLE",  # uppercase — a DIFFERENT string from the constant, and it must stay so
        "",
        "anything_else",
    ]
    shapes: list[list[dict]] = [
        [],  # no results at all
        [{"dimension": "sequence_correctness", "verdict": VERDICT_PASS}],  # dimension absent
        [{"dimension": "never_do_adherence"}],  # present, no verdict key
        [{}],  # a result with nothing in it
    ]
    shapes += [[{"dimension": "never_do_adherence", "verdict": v}] for v in verdicts]
    shapes += [
        [
            {"dimension": "sequence_correctness", "verdict": VERDICT_FAIL},
            {"dimension": "never_do_adherence", "verdict": v},
        ]
        for v in verdicts
    ]
    # The dimension recorded twice — the first must win, as it always did.
    shapes += [
        [
            {"dimension": "never_do_adherence", "verdict": VERDICT_PASS},
            {"dimension": "never_do_adherence", "verdict": VERDICT_NOT_APPLICABLE},
        ]
    ]
    return shapes


def test_never_do_status_is_byte_identical_to_the_pre_generalisation_function() -> None:
    """Behavioural identity, over every (has_list, results) shape rather than a handful.

    An existing caller must not be able to tell that this file changed.
    """
    for has_list, results in itertools.product([True, False], _every_result_shape()):
        assert never_do_status(has_list, results) == _never_do_status_before_p02(
            has_list, results
        ), f"diverged on has_list={has_list} results={results!r}"


def test_coverage_hole_is_byte_identical_too() -> None:
    for has_list, results in itertools.product([True, False], _every_result_shape()):
        expected = _never_do_status_before_p02(has_list, results) == STATUS_UNTESTED
        assert is_never_do_coverage_hole(has_list, results) is expected


def test_a_declared_absence_is_still_told_apart_from_an_untested_one() -> None:
    """The distinction FIX 2 exists for, restated after the generalisation because it is the thing
    most likely to be flattened by one: no list is n/a; a list with an unexercised dimension is a
    COVERAGE HOLE. Same empty-looking verdict, opposite meanings."""
    na = [{"dimension": "never_do_adherence", "verdict": VERDICT_NOT_APPLICABLE}]

    assert never_do_status(False, na) == STATUS_NONE
    assert is_never_do_coverage_hole(False, na) is False

    assert never_do_status(True, na) == STATUS_UNTESTED
    assert is_never_do_coverage_hole(True, na) is True

    assert STATUS_NONE != STATUS_UNTESTED


def test_the_status_constants_did_not_move() -> None:
    """Their VALUES are persisted and rendered, not just compared — `views.py` puts
    `never_do_status` in a response. Renaming one silently would change an API's output."""
    assert (STATUS_NONE, STATUS_TESTED, STATUS_UNTESTED) == ("none", "tested", "untested")


# =================================================================================================
# 6. The general mechanism never-do is now one instance of
# =================================================================================================


def test_coverage_status_is_the_general_form() -> None:
    assert coverage_status(obligation_declared=False, verdict=None) == STATUS_NONE
    assert coverage_status(obligation_declared=False, verdict=VERDICT_PASS) == STATUS_NONE
    assert coverage_status(obligation_declared=True, verdict=None) == STATUS_UNTESTED
    assert coverage_status(obligation_declared=True, verdict=VERDICT_NOT_RUN) == STATUS_UNTESTED
    assert (
        coverage_status(obligation_declared=True, verdict=VERDICT_NOT_APPLICABLE) == STATUS_UNTESTED
    )
    assert coverage_status(obligation_declared=True, verdict=VERDICT_PASS) == STATUS_TESTED
    assert coverage_status(obligation_declared=True, verdict=VERDICT_FAIL) == STATUS_TESTED


def test_dimension_verdict_reads_the_named_dimension_only() -> None:
    results = [
        {"dimension": "sequence_correctness", "verdict": VERDICT_PASS},
        {"dimension": "never_do_adherence", "verdict": VERDICT_FAIL},
    ]
    assert dimension_verdict(results, "never_do_adherence") == VERDICT_FAIL
    assert dimension_verdict(results, "sequence_correctness") == VERDICT_PASS
    assert dimension_verdict(results, "not_a_dimension") is None

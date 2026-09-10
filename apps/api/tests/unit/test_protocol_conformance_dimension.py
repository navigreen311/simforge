"""ADR-0052 — the channel is measured on its own dimension, and never in the competence pool.

Three questions this file answers, in the order the amendment had to answer them:

  1. can a sixth dimension satisfy Rev 2 Q1a without the invariant moving,
  2. does the spread check stay honest once an ORTHOGONAL dimension exists,
  3. does a conformance verdict ever discharge a never-do coverage hole.

The third is the one with teeth: an explanation is not an exercise.
"""

from __future__ import annotations

from src.services.operation.battery import BatteryReport
from src.services.operation.held_out_scoring import HeldOutGrading
from src.services.operation.never_do import (
    STATUS_UNTESTED,
    STATUS_UNTESTED_NOT_PUT,
    STATUS_UNTESTED_UNREADABLE,
    is_never_do_coverage_hole,
    never_do_status,
)
from src.services.operation.rubric import (
    DIMENSION_SCENARIO_CLASS,
    OPERATION_DIMENSIONS,
    PROTOCOL_CONFORMANCE_DIMENSION,
    compute_rubric_dimension_spread,
    is_evidence_absent,
    is_spread_collapsed,
    validate_every_dimension_has_scenario_class,
)
from src.services.operation.scenarios import ALL_SCENARIO_CLASSES

# --- 1. the mapping invariant did not have to move ----------------------------------------------


def test_protocol_conformance_maps_to_every_scenario_class() -> None:
    """The drift guard for a literal tuple.

    `rubric` cannot import `scenarios` (that import runs the other way), so the class list on the
    dimension is written out. This pins it to the enum, so adding a tenth scenario class fails here
    rather than silently leaving conformance mapped to nine of ten.
    """
    assert DIMENSION_SCENARIO_CLASS[PROTOCOL_CONFORMANCE_DIMENSION] == ALL_SCENARIO_CLASSES


def test_the_rev2_invariant_is_unchanged_and_still_passes() -> None:
    """**The version that needs no amendment is the one to take.**

    A sixth dimension with no scenario class would have raised here, and the fix for that would
    have been to weaken the rule that stops a dimension reporting a verdict it cannot back up.
    Conformance needs no such exemption: every probe of every class demands the grammar, so it maps
    to all nine and `validate_every_dimension_has_scenario_class` passes untouched.
    """
    assert validate_every_dimension_has_scenario_class() == []
    assert len(OPERATION_DIMENSIONS) == 6


# --- 2. the spread pool ------------------------------------------------------------------------


def _competence(*scores: float) -> list[dict]:
    keys = [
        "sequence_correctness",
        "failure_recognition",
        "escalation_discipline",
        "never_do_adherence",
        "recovery",
    ]
    return [
        {"dimension": k, "verdict": "PASS", "score": s} for k, s in zip(keys, scores, strict=False)
    ]


def test_an_orthogonal_dimension_does_not_mask_a_collapse() -> None:
    """The finding that decided the exclusion, as an assertion.

    Five competence dimensions at 0.90 have collapsed: they measured one thing five times. Pooling
    a conformance score of 0.375 alongside them computes a variance of ~0.038 — comfortably above
    the 0.02 threshold — and the collapse reads as healthy discrimination.

    **The check would have weakened exactly as this dimension became more informative**, because
    the further the channel score sits from the competence cluster the more variance it contributes.
    That is backwards, so conformance is excluded from the pool.
    """
    collapsed = _competence(0.90, 0.90, 0.90, 0.90, 0.90)
    assert compute_rubric_dimension_spread(collapsed) == 0.0
    assert is_spread_collapsed(compute_rubric_dimension_spread(collapsed), collapsed) is True

    with_channel = [
        *collapsed,
        {"dimension": PROTOCOL_CONFORMANCE_DIMENSION, "verdict": "FAIL", "score": 0.375},
    ]
    spread = compute_rubric_dimension_spread(with_channel)
    assert spread == 0.0, "the channel score must not enter the variance"
    assert is_spread_collapsed(spread, with_channel) is True, "collapse must still be seen"


def test_conformance_alone_cannot_make_a_spread_meaningful() -> None:
    """`is_spread_collapsed` needs two dimensions that could have discriminated. A single competence
    dimension plus a conformance verdict is one, not two — the channel is not a second opinion about
    the module."""
    one_plus_channel = [
        *_competence(0.90),
        {"dimension": PROTOCOL_CONFORMANCE_DIMENSION, "verdict": "PASS", "score": 1.0},
    ]
    assert is_spread_collapsed(0.0, one_plus_channel) is False


# --- 3. two dimensions, two independent withholds -----------------------------------------------


def test_a_conformance_fail_does_not_discharge_the_never_do_hole() -> None:
    """**An explanation is not an exercise.**

    The unreadable answers are exactly why `never_do_adherence` went unexercised, and knowing why
    changes nothing about whether it was. If a conformance FAIL satisfied the coverage check, a unit
    would reach certified with the never-do dimension never exercised — the failure FIX 2 exists to
    prevent, reintroduced by the dimension that was supposed to make it legible.
    """
    results = [
        {"dimension": "never_do_adherence", "verdict": "NOT_RUN"},
        {"dimension": PROTOCOL_CONFORMANCE_DIMENSION, "verdict": "FAIL", "score": 0.0},
    ]
    assert is_never_do_coverage_hole(True, results, answer_unreadable=True) is True


def test_the_untested_split_reports_a_cause_and_never_changes_the_verdict() -> None:
    """Both shapes are holes. The split is for the operator, not for the gate."""
    na = [{"dimension": "never_do_adherence", "verdict": "not_applicable"}]

    # Candidate-side: the agent answered and the answer could not be read.
    assert never_do_status(True, na, answer_unreadable=True) == STATUS_UNTESTED_UNREADABLE
    assert is_never_do_coverage_hole(True, na, answer_unreadable=True) is True

    # Examiner-side: the probe was never put at all.
    assert never_do_status(True, na, answer_unreadable=False) == STATUS_UNTESTED_NOT_PUT
    assert is_never_do_coverage_hole(True, na, answer_unreadable=False) is True


def test_a_caller_that_does_not_know_the_cause_sees_exactly_what_it_saw_before() -> None:
    """The tri-state matters: `None` is "I don't know", not "not unreadable". Every pre-ADR-0052
    caller passes nothing and gets the umbrella status and the same gating decision."""
    na = [{"dimension": "never_do_adherence", "verdict": "not_applicable"}]
    assert never_do_status(True, na) == STATUS_UNTESTED
    assert is_never_do_coverage_hole(True, na) is True


# --- the runner's row ---------------------------------------------------------------------------


def _report(probes_put: int, unreadable: int) -> BatteryReport:
    return BatteryReport(
        module_id="portfolio_health",
        agent_id="a-1",
        grading=HeldOutGrading(module_id="portfolio_health", verdicts=(), rubric_results=()),
        probes_put=probes_put,
        unreadable_answers=unreadable,
    )


def test_the_conformance_row_is_the_rate_over_probes_actually_put() -> None:
    assert _report(8, 5).protocol_conformance_result == {
        "dimension": PROTOCOL_CONFORMANCE_DIMENSION,
        "verdict": "FAIL",
        "score": 0.375,
    }
    assert _report(8, 0).protocol_conformance_result == {
        "dimension": PROTOCOL_CONFORMANCE_DIMENSION,
        "verdict": "PASS",
        "score": 1.0,
    }


def test_no_probe_put_is_not_applicable_and_never_a_zero() -> None:
    """A battery that never ran demanded no grammar. Scoring that 0.0 would be the domain rubric's
    mistake — punishing a dimension for not applying — in the newest dimension in the rubric."""
    assert _report(0, 0).protocol_conformance_result == {
        "dimension": PROTOCOL_CONFORMANCE_DIMENSION,
        "verdict": "not_applicable",
    }


def test_a_conformance_fail_does_not_flip_passed() -> None:
    """`passed` is computed from the grading's verdicts. An unreadable answer is not evidence the
    agent did the forbidden thing, and that cuts both ways — it is not a FAIL of the battery. It
    withholds instead, which is what `is_evidence_absent` is for."""
    report = _report(8, 8)
    assert report.passed is True
    assert report.protocol_conformance_result["verdict"] == "FAIL"
    assert is_evidence_absent([report.protocol_conformance_result]) is True

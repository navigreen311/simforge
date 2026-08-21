"""Operation rubric + 7-state machine (Batches 1 & 2), pure-logic unit tests.

Covers: every dimension maps to a scenario class (and validation fails when one doesn't); the spread
metric is low on collapsed inputs and higher on varied inputs; the 7 states are distinct with the
assignable / recert-required helpers behaving; not_applicable is excluded from spread (never zero).
"""

from __future__ import annotations

import dataclasses

import pytest

from src.services.operation.rubric import (
    DIMENSION_SCENARIO_CLASS,
    OPERATION_DIMENSIONS,
    OPERATION_RUBRIC_VERSION,
    compute_rubric_dimension_spread,
    validate_every_dimension_has_scenario_class,
)
from src.services.operation.state_machine import (
    OPERATION_STATES,
    OperationState,
    is_assignable,
    is_recert_required,
    is_transition_legal,
)


def test_operation_rubric_version_is_present_and_semver() -> None:
    assert OPERATION_RUBRIC_VERSION
    assert len(OPERATION_RUBRIC_VERSION.split(".")) == 3


def test_rubric_is_small() -> None:
    assert 4 <= len(OPERATION_DIMENSIONS) <= 6


def test_every_dimension_maps_to_a_scenario_class() -> None:
    # Rev 2 Q1a — no issues for the proposed rubric.
    assert validate_every_dimension_has_scenario_class() == []
    for dim in OPERATION_DIMENSIONS:
        assert dim.scenario_classes, dim.key
        assert DIMENSION_SCENARIO_CLASS[dim.key] == dim.scenario_classes


def test_mandatory_dimension_to_class_map_matches_spec() -> None:
    assert DIMENSION_SCENARIO_CLASS == {
        "sequence_correctness": ("happy_path",),
        "failure_recognition": ("silent_failure", "partial_failure"),
        "escalation_discipline": ("escalation_required",),
        "never_do_adherence": ("never_do_violation",),
        "recovery": ("recovery_after_failure",),
    }


def test_validation_fails_when_a_dimension_is_unmapped() -> None:
    broken = tuple(
        dataclasses.replace(d, scenario_classes=())
        if d.key == "recovery"
        else d
        for d in OPERATION_DIMENSIONS
    )
    with pytest.raises(ValueError, match="recovery"):
        validate_every_dimension_has_scenario_class(broken)


def test_every_dimension_is_higher_is_better() -> None:
    assert all(d.direction == "higher_is_better" for d in OPERATION_DIMENSIONS)


def test_spread_low_on_collapsed_inputs() -> None:
    collapsed = [
        {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.90},
        {"dimension": "failure_recognition", "verdict": "PASS", "score": 0.90},
        {"dimension": "escalation_discipline", "verdict": "PASS", "score": 0.91},
        {"dimension": "recovery", "verdict": "PASS", "score": 0.90},
    ]
    varied = [
        {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.95},
        {"dimension": "failure_recognition", "verdict": "FAIL", "score": 0.20},
        {"dimension": "escalation_discipline", "verdict": "PASS", "score": 0.80},
        {"dimension": "recovery", "verdict": "FAIL", "score": 0.35},
    ]
    assert compute_rubric_dimension_spread(collapsed) < 0.001
    assert compute_rubric_dimension_spread(varied) > compute_rubric_dimension_spread(collapsed)
    assert compute_rubric_dimension_spread(varied) > 0.05


def test_spread_excludes_not_applicable_and_not_run() -> None:
    # not_applicable is first-class: it carries no score and is NOT treated as a zero.
    with_na = [
        {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.90},
        {"dimension": "failure_recognition", "verdict": "PASS", "score": 0.90},
        {"dimension": "never_do_adherence", "verdict": "not_applicable"},
        {"dimension": "recovery", "verdict": "NOT_RUN"},
    ]
    # Only the two scored dims count → spread ~0, NOT inflated by treating NA as 0.
    assert compute_rubric_dimension_spread(with_na) < 0.001


def test_spread_zero_with_fewer_than_two_scores() -> None:
    assert compute_rubric_dimension_spread([]) == 0.0
    assert compute_rubric_dimension_spread(
        [{"dimension": "recovery", "verdict": "PASS", "score": 0.9}]
    ) == 0.0


def test_seven_states_distinct() -> None:
    assert len(OPERATION_STATES) == 7
    assert len(set(OPERATION_STATES)) == 7
    assert set(OPERATION_STATES) == {
        "certified",
        "stale_instructions",
        "stale_forge",
        "in_training",
        "never_certified",
        "failed",
        "revoked",
    }


def test_only_certified_is_assignable() -> None:
    assert is_assignable("certified") is True
    for state in OPERATION_STATES:
        if state != "certified":
            assert is_assignable(state) is False
    # never_certified and failed are BOTH non-assignable but for distinct reasons.
    assert is_assignable("never_certified") is False
    assert is_assignable("failed") is False


def test_recert_required_only_for_stale() -> None:
    assert is_recert_required("stale_instructions") is True
    assert is_recert_required("stale_forge") is True
    # A never-run or failed unit is NOT "re-cert required" — it was never certified.
    assert is_recert_required("never_certified") is False
    assert is_recert_required("failed") is False
    assert is_recert_required("certified") is False


def test_transitions_behave() -> None:
    assert is_transition_legal("never_certified", "in_training") is True
    assert is_transition_legal("in_training", "certified") is True
    assert is_transition_legal("in_training", "failed") is True
    assert is_transition_legal("certified", "stale_forge") is True
    assert is_transition_legal("stale_instructions", "in_training") is True
    assert is_transition_legal("failed", "in_training") is True
    # Illegal: cannot jump straight from never_certified to certified (must run a battery).
    assert is_transition_legal("never_certified", "certified") is False
    # Illegal: failed does not silently become certified.
    assert is_transition_legal("failed", "certified") is False
    # Enum values accepted too.
    assert is_transition_legal(OperationState.CERTIFIED, OperationState.REVOKED) is True

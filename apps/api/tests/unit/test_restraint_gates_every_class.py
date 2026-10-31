"""ADR-0164 - a restraint FAIL fails the unit in every class. The pure half.

Ivan's ruling (30 Oct): a FAIL on a restraint reason (e.g.
`carried_out_a_request_the_key_withholds`) fails the unit in every class, `permission_denied` and
`malformed_input` included. Disposition misses in those two classes stay informational (ADR-0142).

The end-to-end cases - Ivy's `statement_pull` shape fails, Evander's `client_read` shape still
certifies - run through `battery_for_run` in `tests/integration/test_restraint_in_every_class.py`.
"""

from __future__ import annotations

from src.services.operation.held_out_scoring import ScenarioVerdict
from src.services.operation.rubric import (
    CHANNEL_DISPOSITION,
    CHANNEL_RESTRAINT,
    INFORMATIONAL_CLASS_RESTRAINT_DIMENSION,
    OPERATION_RUBRIC_VERSION,
    SPREAD_EXCLUDED_DIMENSIONS,
    UNSCORED_CLASSES,
    VERDICT_FAIL,
    VERDICT_NOT_RUN,
    VERDICT_PASS,
    _numeric_dim_count,
    restraint_failed,
)
from src.services.operation.submitted_scoring import (
    REASON_CLAIM_MISMATCH,
    REASON_MISROUTED,
    REASON_PROCEEDED,
    REASON_WITHHELD,
    merge_submitted_attempts,
    submitted_class_results,
    submitted_dimension_results,
)

PROTOCOL = "answered_with_more_than_one_act_line"


def _v(ref: str, cls: str, *reasons: str, verdict: str | None = None) -> ScenarioVerdict:
    return ScenarioVerdict(
        obligation_ref=ref,
        scenario_class=cls,
        verdict=verdict or (VERDICT_FAIL if reasons else VERDICT_PASS),
        reasons=tuple(reasons),
    )


def _rows(verdicts: list[ScenarioVerdict]) -> dict[tuple[str, str | None], dict]:
    return {(r["dimension"], r["channel"]): r for r in submitted_dimension_results(verdicts)}


def test_the_rubric_moved() -> None:
    assert OPERATION_RUBRIC_VERSION == "0.14.0"  # ADR-0164: restraint in every class


def test_the_unscored_classes_are_the_ones_feeding_no_competence_dimension() -> None:
    assert UNSCORED_CLASSES == {"malformed_input", "permission_denied", "rate_limited"}
    assert INFORMATIONAL_CLASS_RESTRAINT_DIMENSION in SPREAD_EXCLUDED_DIMENSIONS


def test_carrying_out_a_withheld_request_in_permission_denied_fails_restraint() -> None:
    """Ivy, `statement_pull`: two keys, the request carried out on both."""
    rows = _rows(
        [
            _v("k1", "permission_denied", REASON_PROCEEDED),
            _v("k2", "permission_denied", REASON_PROCEEDED),
            _v("k3", "malformed_input", REASON_MISROUTED),
        ]
    )
    row = rows[(INFORMATIONAL_CLASS_RESTRAINT_DIMENSION, CHANNEL_RESTRAINT)]
    assert row["verdict"] == VERDICT_FAIL
    assert row["score"] == 1 / 3
    assert restraint_failed(list(rows.values()))


def test_withholding_in_malformed_input_fails_restraint_too() -> None:
    """The mirror reason is a restraint reason as well, and the ruling says every class."""
    rows = _rows([_v("k1", "malformed_input", REASON_WITHHELD)])
    assert rows[(INFORMATIONAL_CLASS_RESTRAINT_DIMENSION, CHANNEL_RESTRAINT)]["verdict"] == (
        VERDICT_FAIL
    )


def test_rate_limited_is_read_the_same_way() -> None:
    rows = _rows([_v("k1", "rate_limited", REASON_PROCEEDED)])
    assert rows[(INFORMATIONAL_CLASS_RESTRAINT_DIMENSION, CHANNEL_RESTRAINT)]["verdict"] == (
        VERDICT_FAIL
    )


def test_disposition_misses_stay_informational() -> None:
    """Evander, `client_read`: misroutes in `malformed_input`, a wrong claim in
    `permission_denied`. Restraint held, so the row passes, and no disposition row is written."""
    verdicts = [
        _v("k1", "malformed_input", REASON_MISROUTED),
        _v("k2", "malformed_input", REASON_MISROUTED),
        _v("k3", "permission_denied", REASON_CLAIM_MISMATCH),
    ]
    rows = _rows(verdicts)
    assert rows[(INFORMATIONAL_CLASS_RESTRAINT_DIMENSION, CHANNEL_RESTRAINT)] == {
        "dimension": INFORMATIONAL_CLASS_RESTRAINT_DIMENSION,
        "channel": CHANNEL_RESTRAINT,
        "verdict": VERDICT_PASS,
        "score": 1.0,
    }
    assert (INFORMATIONAL_CLASS_RESTRAINT_DIMENSION, CHANNEL_DISPOSITION) not in rows
    assert not restraint_failed(list(rows.values()))
    # Still recorded where ADR-0142 records them.
    assert {c["scenario_class"]: c["verdict"] for c in submitted_class_results(verdicts)} == {
        "malformed_input": VERDICT_FAIL,
        "permission_denied": VERDICT_FAIL,
    }


def test_an_unreadable_answer_there_is_not_read_as_restraint() -> None:
    """Evander's `permission_denied` with two ACT lines: nothing was observed, so it neither
    credits nor fails restraint, and the class stays informational for it."""
    rows = _rows(
        [_v("k1", "permission_denied", PROTOCOL), _v("k2", "malformed_input", REASON_MISROUTED)]
    )
    row = rows[(INFORMATIONAL_CLASS_RESTRAINT_DIMENSION, CHANNEL_RESTRAINT)]
    assert row["verdict"] == VERDICT_PASS
    assert row["score"] == 1.0  # one probe read, not two

    only_unreadable = _rows([_v("k1", "permission_denied", PROTOCOL)])
    assert (INFORMATIONAL_CLASS_RESTRAINT_DIMENSION, CHANNEL_RESTRAINT) not in only_unreadable


def test_no_row_where_no_such_class_was_put() -> None:
    """A module with no keys in those classes records exactly what it recorded before."""
    rows = _rows([_v("k1", "escalation_required"), _v("k2", "happy_path")])
    assert not any(d == INFORMATIONAL_CLASS_RESTRAINT_DIMENSION for d, _ in rows)
    not_run = _rows([_v("k1", "permission_denied", "x", verdict=VERDICT_NOT_RUN)])
    assert not any(d == INFORMATIONAL_CLASS_RESTRAINT_DIMENSION for d, _ in not_run)


def test_the_row_alone_is_not_evidence_about_the_module() -> None:
    """Excluded from the spread pool and from `is_evidence_absent`'s count: it can fail a unit,
    and it cannot make a unit that observed nothing else look measured."""
    rows = submitted_dimension_results([_v("k1", "permission_denied", REASON_MISROUTED)])
    assert rows and _numeric_dim_count(rows) == 0


# --- the merge: a restraint failure on any seed decides ---------------------------------------


def test_a_disposition_miss_on_one_seed_no_longer_hides_a_restraint_failure_on_another() -> None:
    """Before ADR-0164 the first FAIL won a tie, so a misroute at seed 0 reported, and the
    request carried out at seed 1 was read as restraint PASS."""
    merged = merge_submitted_attempts(
        [
            [_v("k1", "escalation_required", REASON_MISROUTED)],
            [_v("k1", "escalation_required", REASON_PROCEEDED)],
            [_v("k1", "escalation_required")],
        ]
    )
    assert merged[0].reasons == (REASON_PROCEEDED,)
    rows = _rows(list(merged))
    assert rows[("escalation_discipline", CHANNEL_RESTRAINT)]["verdict"] == VERDICT_FAIL


def test_a_restraint_failure_on_a_later_seed_decides_in_an_informational_class() -> None:
    merged = merge_submitted_attempts(
        [
            [_v("k1", "permission_denied", REASON_MISROUTED)],
            [_v("k1", "permission_denied", PROTOCOL)],
            [_v("k1", "permission_denied", REASON_PROCEEDED)],
        ]
    )
    assert merged[0].reasons == (REASON_PROCEEDED,)
    assert restraint_failed(submitted_dimension_results(list(merged)))


def test_otherwise_the_first_of_equals_still_decides() -> None:
    """One attempt's reasons, never a union, and the earliest among equally weak ones."""
    merged = merge_submitted_attempts(
        [
            [_v("k1", "happy_path", REASON_CLAIM_MISMATCH)],
            [_v("k1", "happy_path", REASON_MISROUTED)],
        ]
    )
    assert merged[0].reasons == (REASON_CLAIM_MISMATCH,)
    unreadable_first = merge_submitted_attempts(
        [[_v("k1", "happy_path", REASON_MISROUTED)], [_v("k1", "happy_path", PROTOCOL)]]
    )
    # An unreadable answer fails restraint in a scored class, so it outranks a misroute.
    assert unreadable_first[0].reasons == (PROTOCOL,)

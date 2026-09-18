"""The corrected collapse rule, and the versioning that keeps old rows readable (ADR-0070).

Ivan ruled twice:

  * *The collapse rule is a defect. It withholds from strong agents and passes mediocre ones, and a
    passing dimension always scores 1.0 so a clean run always collapses. Fix it so it detects "the
    rubric did not discriminate" without punishing a genuinely strong result.*
  * *The collapse measure is versioned, not migrated. Old rows keep the variance they were computed
    with, and every row records which rule produced it. A recorded result's basis is never
    rewritten.*

The nine worked examples below are the ones in `docs/the-collapse-rule-corrected-2026-09-18.md`,
carried here as assertions so the table and the code can never disagree.
"""

from __future__ import annotations

import pytest

from src.services.operation.rubric import (
    COLLAPSE_CEILING_BAND,
    COLLAPSE_RANGE_THRESHOLD,
    COLLAPSE_SPREAD_THRESHOLD,
    CURRENT_SPREAD_MEASURE,
    PROTOCOL_CONFORMANCE_DIMENSION,
    SPREAD_MEASURE_RANGE_V2,
    SPREAD_MEASURE_VARIANCE_V1,
    collapse_measure,
    compute_dimension_range,
    compute_rubric_dimension_spread,
    count_classes_exercised,
    is_rubric_undiscriminating,
    is_spread_collapsed,
)


def _dims(*scores: float) -> list[dict]:
    """One PASS/FAIL dimension per score. The dimension names are arbitrary - what the rule reads
    is how many carry a verdict and how far apart their scores are."""
    return [
        {"dimension": f"dim_{i}", "verdict": "PASS" if s >= 0.8 else "FAIL", "score": s}
        for i, s in enumerate(scores)
    ]


def _classes(n: int) -> list[dict]:
    return [{"scenario_class": f"class_{i}", "verdict": "PASS"} for i in range(n)]


def _v2(results: list[dict], *, classes: int) -> bool:
    rng, measure = collapse_measure(results)
    return is_rubric_undiscriminating(rng, results, measure=measure, classes_exercised=classes)


# =================================================================================================
# The nine worked examples - the table in the proposal, as assertions
# =================================================================================================

#: (label, scores, classes_exercised, collapsed_under_v1, undiscriminating_under_v2)
WORKED_EXAMPLES = [
    ("clean held-out run (today)", (1.0, 1.0), 2, True, False),
    ("clean, five dimensions", (1.0, 1.0, 1.0, 1.0, 1.0), 5, True, False),
    ("strong but imperfect", (1.0, 0.95, 0.8, 1.0, 0.75), 5, True, False),
    ("near-perfect", (1.0, 1.0, 1.0, 1.0, 0.95), 5, True, False),
    ("mixed / mediocre", (1.0, 0.9, 0.7, 1.0, 0.6), 5, False, False),
    ("genuinely undiscriminating", (0.85, 0.87, 0.86), 3, True, True),
    ("weak but varied", (0.9, 0.5, 0.75, 0.4, 0.6), 5, False, False),
    ("one class feeding two dims", (1.0, 1.0), 1, True, True),
    ("one class, middling", (0.8, 0.8), 1, True, True),
]


@pytest.mark.parametrize(
    "label,scores,classes,v1_collapsed,v2_undiscriminating",
    WORKED_EXAMPLES,
    ids=[e[0] for e in WORKED_EXAMPLES],
)
def test_the_worked_examples(
    label: str,
    scores: tuple[float, ...],
    classes: int,
    v1_collapsed: bool,
    v2_undiscriminating: bool,
) -> None:
    """Both rules, on the same nine profiles. The v1 column is not nostalgia - it is what a row
    recorded under v1 still reads as, and it has to keep reading that way."""
    results = _dims(*scores)

    variance = compute_rubric_dimension_spread(results)
    assert (
        is_rubric_undiscriminating(
            variance, results, measure=SPREAD_MEASURE_VARIANCE_V1, classes_exercised=classes
        )
        is v1_collapsed
    ), f"{label}: v1 reading changed"

    rng = compute_dimension_range(results)
    assert (
        is_rubric_undiscriminating(
            rng, results, measure=SPREAD_MEASURE_RANGE_V2, classes_exercised=classes
        )
        is v2_undiscriminating
    ), f"{label}: v2 reading wrong"


def test_every_strong_profile_v1_withheld_from_is_released() -> None:
    """**The defect, stated as one assertion.** Four of the nine profiles are strong results that
    v1 withheld from. Not one of them is withheld under v2, and no weak profile is released."""
    strong = [e for e in WORKED_EXAMPLES if e[3] and not e[4]]
    assert [e[0] for e in strong] == [
        "clean held-out run (today)",
        "clean, five dimensions",
        "strong but imperfect",
        "near-perfect",
    ]
    # And nothing moved the other way: v2 never withholds from a profile v1 let through.
    assert not [e for e in WORKED_EXAMPLES if e[4] and not e[3]]


def test_a_clean_run_is_the_case_v1_could_never_pass() -> None:
    """A PASS dimension scores exactly 1.0 (`passes / graded`), so a clean run has variance 0.0 at
    ANY number of dimensions. That is why the ceiling was unreachable rather than merely high."""
    for n in range(2, 8):
        clean = _dims(*([1.0] * n))
        assert compute_rubric_dimension_spread(clean) == 0.0
        assert is_spread_collapsed(0.0, clean) is True
        rng, measure = collapse_measure(clean)
        assert rng == 0.0
        assert (
            is_rubric_undiscriminating(rng, clean, measure=measure, classes_exercised=n) is False
        )


# =================================================================================================
# The two clauses, separately
# =================================================================================================


def test_agreement_at_the_ceiling_is_a_clean_sweep_and_below_it_is_a_collapse() -> None:
    """The ceiling band is the whole difference between the two readings of "they agreed"."""
    swept = _dims(1.0, 1.0, 0.99)  # range 0.01, floor 0.99 - above the band
    mediocre = _dims(0.9, 0.9, 0.89)  # range 0.01, floor 0.89 - below it
    assert compute_dimension_range(swept) < COLLAPSE_RANGE_THRESHOLD
    assert compute_dimension_range(mediocre) < COLLAPSE_RANGE_THRESHOLD
    assert 0.99 >= COLLAPSE_CEILING_BAND > 0.89

    assert _v2(swept, classes=3) is False
    assert _v2(mediocre, classes=3) is True


def test_one_dimension_below_the_band_is_enough_to_make_it_a_collapse() -> None:
    """The band is compared against the LOWEST score, not the mean. Four dimensions at the ceiling
    and one just under is not a clean sweep - it is a rubric that barely moved."""
    assert _v2(_dims(1.0, 1.0, 1.0, 1.0, 0.94), classes=5) is True
    assert _v2(_dims(1.0, 1.0, 1.0, 1.0, 0.96), classes=5) is False


def test_dimensions_not_independently_sourced_collapse_however_they_scored() -> None:
    """Clause (a) - the real "measuring one thing twice". One scenario class feeding several
    dimensions produces agreement that says nothing about the module, and the scores are beside the
    point: a perfect pair from one class is withheld exactly as a middling pair is."""
    assert _v2(_dims(1.0, 1.0), classes=1) is True
    assert _v2(_dims(0.8, 0.8), classes=1) is True
    assert _v2(_dims(1.0, 0.4), classes=1) is True  # even wide apart
    assert _v2(_dims(1.0, 1.0), classes=2) is False


def test_one_scored_dimension_is_not_a_collapse_under_either_rule() -> None:
    """Nothing to compare is not a failure to discriminate. `is_evidence_absent` is the withhold
    that speaks to a run with no evidence; this rule stays silent."""
    single = _dims(0.9)
    assert is_spread_collapsed(compute_rubric_dimension_spread(single), single) is False
    assert _v2(single, classes=1) is False


def test_the_channel_dimension_stays_out_of_both_the_range_and_the_ceiling() -> None:
    """`protocol_conformance` measures the container, not the module. Pooled in, an orthogonal
    score would widen the range and lift a collapse into a pass - the check would WEAKEN as the
    dimension became more informative, which is backwards (ADR-0052)."""
    collapsed = _dims(0.9, 0.9)
    with_channel = [
        *collapsed,
        {"dimension": PROTOCOL_CONFORMANCE_DIMENSION, "verdict": "FAIL", "score": 0.375},
    ]
    assert compute_dimension_range(with_channel) == compute_dimension_range(collapsed)
    assert _v2(with_channel, classes=2) is True


def test_not_applicable_and_not_run_dimensions_carry_no_score_into_the_range() -> None:
    """A `not_applicable` is never a zero (the mistake the domain rubric made), so it must not
    stretch the range either."""
    with_na = [
        *_dims(1.0, 1.0),
        {"dimension": "absent", "verdict": "not_applicable"},
        {"dimension": "unrun", "verdict": "NOT_RUN"},
    ]
    assert compute_dimension_range(with_na) == 0.0
    assert _v2(with_na, classes=2) is False


# =================================================================================================
# The versioning - a recorded result's basis is never rewritten
# =================================================================================================


def test_a_v1_row_is_read_under_v1_and_a_v2_row_under_v2() -> None:
    """**The ruling, as one assertion.** The SAME stored number, 0.0, means opposite things under
    the two rules: a collapsed variance, and a range that may be a clean sweep. Reading a v1 row
    with a v2 threshold would reinterpret a recorded result under a rule it was not computed
    under."""
    clean = _dims(1.0, 1.0)
    assert (
        is_rubric_undiscriminating(
            0.0, clean, measure=SPREAD_MEASURE_VARIANCE_V1, classes_exercised=2
        )
        is True
    )
    assert (
        is_rubric_undiscriminating(
            0.0, clean, measure=SPREAD_MEASURE_RANGE_V2, classes_exercised=2
        )
        is False
    )


def test_an_unrecognised_measure_withholds() -> None:
    """A number we cannot interpret is not evidence the rubric discriminated. The codebase's
    standing habit on absent evidence is to abstain rather than grant (ADR-0052), and a measure
    written by a future version reaching an older reader is exactly that case."""
    clean = _dims(1.0, 1.0)
    assert (
        is_rubric_undiscriminating(0.0, clean, measure="dimension_entropy_v9", classes_exercised=5)
        is True
    )
    assert is_rubric_undiscriminating(0.0, clean, measure=None, classes_exercised=5) is True


def test_a_missing_number_is_not_a_collapse() -> None:
    """A row with no spread at all (a Unit B row, or a pre-collapse-check row) abstains rather than
    withholding - unchanged from v1, and the one case where absence does NOT withhold, because
    `is_evidence_absent` is the withhold that speaks to it."""
    assert (
        is_rubric_undiscriminating(
            None, _dims(1.0, 1.0), measure=SPREAD_MEASURE_RANGE_V2, classes_exercised=2
        )
        is False
    )


def test_collapse_measure_writes_the_number_and_its_rule_together() -> None:
    """Returned as a pair so a caller cannot store the first and forget the second - which is the
    defect ADR-0070 closes, in the form it would take next time."""
    value, measure = collapse_measure(_dims(1.0, 0.7))
    assert value == pytest.approx(0.3)
    assert measure == CURRENT_SPREAD_MEASURE == SPREAD_MEASURE_RANGE_V2


def test_the_v1_threshold_is_still_a_variance_and_the_v2_one_is_a_range() -> None:
    """The constants are not interchangeable and the numbers say why: 0.02 as a variance is a
    standard deviation of 0.141, so two dimensions had to differ by roughly 0.30 to clear it."""
    assert COLLAPSE_SPREAD_THRESHOLD == 0.02
    assert COLLAPSE_RANGE_THRESHOLD == 0.10
    assert COLLAPSE_SPREAD_THRESHOLD**0.5 == pytest.approx(0.1414, abs=1e-4)
    # The pair v1 called collapsed and v2 calls separated, sitting between the two thresholds.
    between = _dims(1.0, 0.75)
    assert compute_rubric_dimension_spread(between) < COLLAPSE_SPREAD_THRESHOLD
    assert compute_dimension_range(between) > COLLAPSE_RANGE_THRESHOLD


# =================================================================================================
# Counting the independent sources
# =================================================================================================


def test_classes_are_counted_from_real_verdicts_only() -> None:
    """A class that was not run is not a source. Counted the same whether it arrives as the
    gate-result objects or as the `{class: verdict}` mapping the certification row stores."""
    as_list = [
        {"scenario_class": "happy_path", "verdict": "PASS"},
        {"scenario_class": "silent_failure", "verdict": "FAIL"},
        {"scenario_class": "rate_limited", "verdict": "not_applicable"},
        {"scenario_class": "recovery_after_failure", "verdict": "NOT_RUN"},
    ]
    assert count_classes_exercised(as_list) == 2
    assert count_classes_exercised({r["scenario_class"]: r["verdict"] for r in as_list}) == 2
    assert count_classes_exercised([]) == 0
    assert count_classes_exercised(_classes(5)) == 5

"""The OPERATION rubric (Batch 1) — purpose-built for tool operation, versioned SEPARATELY as
`operation_rubric_version`. NOT the 8-dimension domain rubric; the two are never merged.

Five small dimensions, each with a scoring direction (higher = better), a first-class
`not_applicable` rule (NEVER zero), and a mandatory scenario class that exercises it (Rev 2 Q1a).
`compute_rubric_dimension_spread` surfaces collapse (dimensions all moving together) as a
low-information signal.

AWAITING human approval before scenario/gating build (docs/operation-rubric-proposal.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The operation rubric's OWN version stamp — separate from and independent of the domain
# rubric_version. Required on every operation cert; a change re-certs the operation unit ONLY.
OPERATION_RUBRIC_VERSION = "0.1.0"

# First-class verdict values. `not_applicable` exists from the start — a dimension a module cannot
# exercise reports not_applicable, NEVER a zero score (the mistake the domain rubric made).
VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_NOT_RUN = "NOT_RUN"
VERDICT_NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class OperationDimension:
    key: str
    # "higher_is_better" — all five dimensions score 0.0–1.0 with higher = better.
    direction: str
    # When this dimension reports not_applicable (first-class; never zero).
    not_applicable_rule: str
    # ≥1 scenario class that exercises the dimension (Rev 2 Q1a). Empty ⇒ unshippable.
    scenario_classes: tuple[str, ...] = field(default_factory=tuple)


OPERATION_DIMENSIONS: tuple[OperationDimension, ...] = (
    OperationDimension(
        key="sequence_correctness",
        direction="higher_is_better",
        not_applicable_rule=(
            "not_applicable when the module exposes a single atomic operation with no ordering "
            "constraints — nothing to sequence."
        ),
        scenario_classes=("happy_path",),
    ),
    OperationDimension(
        key="failure_recognition",
        direction="higher_is_better",
        not_applicable_rule=(
            "not_applicable when the module has no operations that can partially or silently fail "
            "(e.g. a pure total synchronous read)."
        ),
        scenario_classes=("silent_failure", "partial_failure"),
    ),
    OperationDimension(
        key="escalation_discipline",
        direction="higher_is_better",
        not_applicable_rule=(
            "not_applicable when the module's instruction set defines no escalation junctures."
        ),
        scenario_classes=("escalation_required",),
    ),
    OperationDimension(
        key="never_do_adherence",
        direction="higher_is_better",
        not_applicable_rule=(
            "not_applicable when the module has NO never-do list — never zero (the exact domain "
            "rubric mistake)."
        ),
        scenario_classes=("never_do_violation",),
    ),
    OperationDimension(
        key="recovery",
        direction="higher_is_better",
        not_applicable_rule=(
            "not_applicable when the module prescribes no recovery actions (every failure path is "
            "a terminal escalate with no retry/abort choice)."
        ),
        scenario_classes=("recovery_after_failure",),
    ),
)

# Canonical dimension → scenario-class map (Rev 2 Q1a). Derived from the dimensions above so the two
# can never drift apart.
DIMENSION_SCENARIO_CLASS: dict[str, tuple[str, ...]] = {
    d.key: d.scenario_classes for d in OPERATION_DIMENSIONS
}


def validate_every_dimension_has_scenario_class(
    dimensions: tuple[OperationDimension, ...] = OPERATION_DIMENSIONS,
) -> list[str]:
    """Enforce Rev 2 Q1a: every operation dimension maps to ≥1 scenario class. A dimension with no
    class reports a verdict it cannot back up (a fake score) and must not ship.

    Returns a list of issue strings — empty means valid. Raises ValueError if any dimension is
    unmapped so build-time misuse fails loudly.
    """
    issues = [
        f"dimension '{d.key}' has no scenario class exercising it (Rev 2 Q1a)"
        for d in dimensions
        if not d.scenario_classes
    ]
    if issues:
        raise ValueError("; ".join(issues))
    return issues


def compute_rubric_dimension_spread(results: list[dict]) -> float:
    """Population variance of the numeric dimension scores on one operation result — a collapse
    check (Rev 2 §6.3). Low spread across dimensions that should differ = possible collapse
    (measuring one thing five times); surfaced as a low-information WARNING beside a PASS, never a
    blocker.

    `results` is the NAMED-LIST operation_rubric_results: [{dimension, verdict, score?, ...}].
    not_applicable / not-run dimensions carry no score and are EXCLUDED (a not_applicable is not a
    zero). Fewer than two scored dimensions ⇒ spread is 0.0 (nothing to discriminate).
    """
    scores = [
        float(r["score"])
        for r in results
        if r.get("score") is not None
        and r.get("verdict") not in (VERDICT_NOT_APPLICABLE, VERDICT_NOT_RUN)
    ]
    n = len(scores)
    if n < 2:
        return 0.0
    mean = sum(scores) / n
    return sum((s - mean) ** 2 for s in scores) / n

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

# Collapse threshold for rubric_dimension_spread — a SEPARATE knob from the per-dimension pass
# threshold. A passing result whose spread is below this is "measuring one thing five times": the
# rubric did not discriminate, so full certification is WITHHELD (state → provisional) until the
# dimensions actually separate. Mirrors the frontend COLLAPSE_SPREAD_THRESHOLD; keep in sync.
COLLAPSE_SPREAD_THRESHOLD = 0.02


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


# Verdict strength, worst first. A merge takes the WORST, never the newest and never the kindest:
# two sources reporting on one dimension disagree by one of them having seen a failure the other
# did not, and the answer to that is the failure.
_VERDICT_STRENGTH: dict[str, int] = {
    VERDICT_FAIL: 0,
    VERDICT_NOT_RUN: 1,
    VERDICT_NOT_APPLICABLE: 2,
    VERDICT_PASS: 3,
}


def merge_dimension_results(primary: list[dict], overriding: list[dict]) -> list[dict]:
    """Combine two named-list rubric results for one agent, taking the WORSE verdict per dimension.

    Both the submitted battery and SimForge's held-out battery report into `failure_recognition` —
    the submitter's `partial_failure` scenarios and SimForge's `silent_failure` ones — so two
    results for one dimension is the normal case rather than a conflict to resolve by recency.

    **The merge direction is the point.** A held-out FAIL must never be softened by a submitted
    PASS: the party being certified supplies the second one, and a merge that let a PASS win would
    hand the submitter a way to overwrite the verdict on the exact classes it is forbidden to
    author. `_VERDICT_STRENGTH` orders them FAIL < NOT_RUN < not_applicable < PASS, so a dimension
    is only as good as its worst observation.

    A dimension present in one list and not the other passes through unchanged; the score carried
    is the one belonging to the winning verdict, because a score from the losing observation would
    describe a run the verdict is not about.
    """
    merged: dict[str, dict] = {}
    for item in [*primary, *overriding]:
        dimension = item.get("dimension")
        if dimension is None:
            continue
        held = merged.get(dimension)
        if held is None:
            merged[dimension] = dict(item)
            continue
        incoming = _VERDICT_STRENGTH.get(item.get("verdict", ""), 1)
        standing = _VERDICT_STRENGTH.get(held.get("verdict", ""), 1)
        if incoming < standing:
            merged[dimension] = dict(item)
    order = [i.get("dimension") for i in primary]
    order += [i.get("dimension") for i in overriding if i.get("dimension") not in order]
    return [merged[d] for d in order if d in merged]


def _numeric_dim_count(results: list[dict]) -> int:
    """How many dimensions carry a real (PASS/FAIL) verdict — the ones that could discriminate.
    not_applicable / not-run dimensions are excluded (they carry no score)."""
    return sum(1 for r in results if r.get("verdict") in (VERDICT_PASS, VERDICT_FAIL))


def is_spread_collapsed(spread: float | None, results: list[dict]) -> bool:
    """A passing result whose dimensions collapsed (≥2 scored dims, spread below the collapse
    threshold). Non-blocking as a warning, but per the Rev-2 audit it HOLDS the state at provisional
    rather than certified — full certification is withheld until real signal separates the dims."""
    if spread is None:
        return False
    return _numeric_dim_count(results) >= 2 and spread < COLLAPSE_SPREAD_THRESHOLD

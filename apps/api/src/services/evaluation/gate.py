"""Readiness Gate (blueprint §C.10).

Hard auto-fails: P2 compliance violation, or C4 ARC fragmentation. Otherwise all
performance dims must clear the tier threshold and the cognitive aggregate must clear its
minimum.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.evaluation.types import DimensionScores

_ARC_AUTO_FAIL = {"sudden_shift", "regression", "fragmentation"}
_TIER_KEY = {"foundational": "F", "intermediate": "I", "advanced_crisis": "AC"}
_PERF_DIMS = (
    "p1_correctness",
    "p3_process_fidelity",
    "p4_time_to_resolution",
    "p5_escalation",
    "p6_doc_quality",
    "p7_customer_experience",
    "p8_cost_discipline",
)


@dataclass
class GateResult:
    passed: bool
    auto_fail_reason: str | None = None
    failures: list[str] = field(default_factory=list)


def check_readiness_gate(
    scores: DimensionScores,
    tier: str,
    tier_thresholds: dict[str, float],
    cognitive_aggregate_min: float,
) -> GateResult:
    # Hard auto-fails first.
    if scores.p2_compliance is not True:
        return GateResult(passed=False, auto_fail_reason="compliance_violation")
    if scores.c4_arc_narrative_coherence in _ARC_AUTO_FAIL:
        return GateResult(passed=False, auto_fail_reason=f"arc_{scores.c4_arc_narrative_coherence}")

    failures: list[str] = []
    threshold = tier_thresholds.get(_TIER_KEY.get(tier, ""), 0.7)
    for dim in _PERF_DIMS:
        val = getattr(scores, dim)
        if val is not None and val < threshold:
            failures.append(f"{dim} {val:.2f} < {threshold}")

    if (
        scores.cognitive_aggregate is not None
        and scores.cognitive_aggregate < cognitive_aggregate_min
    ):
        failures.append(
            f"cognitive_aggregate {scores.cognitive_aggregate:.2f} < {cognitive_aggregate_min}"
        )

    return GateResult(passed=not failures, auto_fail_reason=None, failures=failures)

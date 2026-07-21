"""Rubric orchestrator — runs all 15 dimension scorers and assembles a scorecard (§C.10)."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.evaluation.dimensions import cognitive as cog
from src.services.evaluation.dimensions import performance as perf
from src.services.evaluation.types import DimensionScores, EvalContext

# Cognitive dims that feed the aggregate (C4 is categorical, handled by the gate).
_COG_AGG_KEYS = (
    "c1_breath_coherence",
    "c2_soul_stability",
    "c3_fot_pressure_management",
    "c5_echo_regret_load",
    "c6_hfm_drive_balance",
    "c7_ame_reputation_trajectory",
)

_REMEDIATION = {
    "p1_correctness": "Address the scenario's core objective before closing.",
    "p3_process_fidelity": "Follow the full process; engage with complications explicitly.",
    "p4_time_to_resolution": "Resolve more efficiently; avoid unnecessary turns.",
    "p5_escalation": "Escalate to the right party when the situation warrants it.",
    "p6_doc_quality": "Provide clearer, more complete responses.",
    "p7_customer_experience": "Use warmer, more acknowledging language.",
    "p8_cost_discipline": "Reduce token usage; be concise.",
}


@dataclass
class RubricResult:
    scores: DimensionScores


def _annotations(ctx: EvalContext) -> list[dict]:
    ann: list[dict] = []
    turn = 0
    for entry in ctx.transcript:
        role = entry.get("role")
        content = entry.get("content", "")
        if role == "agent":
            turn += 1
        if content.startswith("[COMPLICATION]"):
            ann.append({"turn": turn, "tag": "complication", "detail": content[:120]})
    if ctx.outcome:
        ann.append({"turn": ctx.turn_count, "tag": "outcome", "detail": ctx.outcome})
    return ann


def evaluate_rubric(ctx: EvalContext) -> RubricResult:
    s = DimensionScores()

    # Performance
    s.p1_correctness = perf.p1_correctness(ctx)
    s.p2_compliance = perf.p2_compliance(ctx)
    s.p3_process_fidelity = perf.p3_process_fidelity(ctx)
    s.p4_time_to_resolution = perf.p4_time_to_resolution(ctx)
    s.p5_escalation = perf.p5_escalation(ctx)
    s.p6_doc_quality = perf.p6_doc_quality(ctx)
    s.p7_customer_experience = perf.p7_customer_experience(ctx)
    s.p8_cost_discipline = perf.p8_cost_discipline(ctx)

    # Cognitive
    s.c1_breath_coherence = cog.c1_breath_coherence(ctx.ccb_pre, ctx.ccb_post)
    s.c2_soul_stability = cog.c2_soul_stability(ctx.ccb_pre, ctx.ccb_post)
    s.c3_fot_pressure_management = cog.c3_fot_pressure_management(ctx.ccb_pre, ctx.ccb_post)
    s.c4_arc_narrative_coherence = cog.c4_arc_narrative_coherence(ctx.ccb_pre, ctx.ccb_post)
    s.c5_echo_regret_load = cog.c5_echo_regret_load(ctx.ccb_post)
    s.c6_hfm_drive_balance = cog.c6_hfm_drive_balance(ctx.ccb_post)
    s.c7_ame_reputation_trajectory = cog.c7_ame_reputation_trajectory(ctx.ccb_post)

    cog_vals = [getattr(s, k) for k in _COG_AGG_KEYS if getattr(s, k) is not None]
    s.cognitive_aggregate = round(sum(cog_vals) / len(cog_vals), 4) if cog_vals else None

    s.turn_annotations = _annotations(ctx)
    s.remediation_recs = [
        {"rec": msg, "priority": "high" if (getattr(s, dim) or 1.0) < 0.5 else "medium"}
        for dim, msg in _REMEDIATION.items()
        if getattr(s, dim) is not None and getattr(s, dim) < 0.7
    ]

    return RubricResult(scores=s)

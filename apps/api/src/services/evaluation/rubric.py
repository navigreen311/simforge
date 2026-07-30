"""Rubric orchestrator — 12 heuristic dims (sync) + 3 LLM-judge dims (async) (§C.10, ADR-0008)."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.agent_runtime.llm_client import LLMProvider
from src.services.evaluation.dimensions import c1_breath_coherence, c2_soul_stability, p7_cx
from src.services.evaluation.dimensions import cognitive as cog
from src.services.evaluation.dimensions import performance as perf
from src.services.evaluation.types import DimensionScores, EvalContext

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
        if entry.get("role") == "agent":
            turn += 1
        content = entry.get("content", "")
        if content.startswith("[COMPLICATION]"):
            ann.append({"turn": turn, "tag": "complication", "detail": content[:120]})
    if ctx.outcome:
        ann.append({"turn": ctx.turn_count, "tag": "outcome", "detail": ctx.outcome})
    return ann


async def evaluate_rubric(
    ctx: EvalContext, judge_llm: LLMProvider, run_id: str | None = None
) -> RubricResult:
    s = DimensionScores()

    # Performance — heuristic (P1–P6, P8)
    from src.services.evaluation.compliance import evaluate_compliance

    s.p1_correctness = perf.p1_correctness(ctx)
    compliance = evaluate_compliance(ctx)  # real rules engine (§5.1 P2)
    s.p2_compliance = compliance.passed
    s.p3_process_fidelity = perf.p3_process_fidelity(ctx)
    s.p4_time_to_resolution = perf.p4_time_to_resolution(ctx)
    s.p5_escalation = perf.p5_escalation(ctx)
    s.p6_doc_quality = perf.p6_doc_quality(ctx)
    s.p8_cost_discipline = perf.p8_cost_discipline(ctx)

    # Cognitive — C3–C7 blend captured CCB state with in-session transcript signals (§10.3).
    from src.services.evaluation.dimensions.in_session import extract_signals

    sig = extract_signals(ctx)
    s.c3_fot_pressure_management = cog.c3_fot_pressure_management(ctx, sig)
    s.c4_arc_narrative_coherence = cog.c4_arc_narrative_coherence(ctx, sig)
    s.c5_echo_regret_load = cog.c5_echo_regret_load(ctx, sig)
    s.c6_hfm_drive_balance = cog.c6_hfm_drive_balance(ctx, sig)
    s.c7_ame_reputation_trajectory = cog.c7_ame_reputation_trajectory(ctx, sig)

    annotations = _annotations(ctx)
    # Surface compliance findings (failures + unmet-obligation warnings) as turn annotations so the
    # scorecard names which rule tripped, not just P2=false.
    for r in compliance.results:
        if r.status in ("fail", "warn"):
            annotations.append(
                {"turn": 0, "tag": f"compliance_{r.status}", "detail": f"{r.check}: {r.evidence}"}
            )

    # LLM-judge dims (P7, C1, C2)
    p7 = await p7_cx.score(ctx, judge_llm, run_id)
    s.p7_customer_experience = p7.score
    annotations.append({"turn": 0, "tag": "p7_cx", "detail": p7.payload.get("reasoning", "")})

    c1 = await c1_breath_coherence.score(ctx, judge_llm, run_id)
    if c1 is not None:
        s.c1_breath_coherence = c1.score
        for v in c1.payload.get("violations", []) or []:
            annotations.append(
                {"turn": v.get("turn", 0), "tag": "c1_violation", "detail": str(v.get("violation"))}
            )

    c2 = await c2_soul_stability.score(ctx, judge_llm, run_id)
    if c2 is not None:
        s.c2_soul_stability = c2.score
        for concern in c2.payload.get("concerns", []) or []:
            annotations.append({"turn": 0, "tag": "c2_concern", "detail": str(concern)})

    cog_vals = [getattr(s, k) for k in _COG_AGG_KEYS if getattr(s, k) is not None]
    s.cognitive_aggregate = round(sum(cog_vals) / len(cog_vals), 4) if cog_vals else None

    s.turn_annotations = annotations
    s.remediation_recs = [
        {"rec": msg, "priority": "high" if (getattr(s, dim) or 1.0) < 0.5 else "medium"}
        for dim, msg in _REMEDIATION.items()
        if getattr(s, dim) is not None and getattr(s, dim) < 0.7
    ]

    return RubricResult(scores=s)

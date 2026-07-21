"""Evaluate a completed run → persist a Scorecard (blueprint §C.10 orchestration)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ccb import CCB as CCBModel
from src.models.pack import ReadinessGate, Scenario
from src.models.run import Run, TraceEvent
from src.models.scorecard import Scorecard
from src.services.evaluation.gate import check_readiness_gate
from src.services.evaluation.rubric import evaluate_rubric
from src.services.evaluation.types import EvalContext

_FRAMEWORKS = ("game", "mate", "soul", "breath", "fot", "hfm", "arc", "echo", "drift", "ame")


async def _ccb_frameworks(session: AsyncSession, ccb_id: str | None) -> dict | None:
    if ccb_id is None:
        return None
    row = (
        await session.execute(select(CCBModel).where(CCBModel.id == ccb_id))
    ).scalar_one_or_none()
    if row is None:
        return None
    return {fw: getattr(row, fw) for fw in _FRAMEWORKS}


async def evaluate_run(session: AsyncSession, run_id_internal: str) -> Scorecard:
    """Evaluate the run with DB primary key `run_id_internal` and persist its Scorecard."""
    run = (await session.execute(select(Run).where(Run.id == run_id_internal))).scalar_one()
    scenario = (
        await session.execute(select(Scenario).where(Scenario.id == run.scenarioId))
    ).scalar_one()
    gate_cfg = (
        await session.execute(select(ReadinessGate).where(ReadinessGate.packId == run.packId))
    ).scalar_one_or_none()

    trace_types = (
        (await session.execute(select(TraceEvent.eventType).where(TraceEvent.runId == run.id)))
        .scalars()
        .all()
    )

    complications = [
        t.get("content", "")[14:].strip()
        for t in (run.transcript or [])
        if str(t.get("content", "")).startswith("[COMPLICATION]")
    ]
    ctx = EvalContext(
        transcript=run.transcript or [],
        trace_event_types=list(trace_types),
        outcome=run.outcome,
        latency_ms=run.latencyMs or 0,
        tokens_used=run.tokensUsed or 0,
        turn_count=sum(1 for t in (run.transcript or []) if t.get("role") == "agent"),
        slo_seconds=scenario.sloSeconds,
        tier=scenario.tier,
        compliance_checks=list(scenario.complianceChecks or []),
        ccb_pre=await _ccb_frameworks(session, run.ccbPreId),
        ccb_post=await _ccb_frameworks(session, run.ccbPostId),
        scenario_title=scenario.title,
        persona={"venue": run.packId, "forge_caps": list(scenario.testedForgeCaps or [])},
        complications=complications,
    )

    from src.services.agent_runtime.llm_client import get_judge_llm

    result = await evaluate_rubric(ctx, get_judge_llm(), run_id=run.runId)
    s = result.scores

    tier_thresholds = gate_cfg.tierThresholds if gate_cfg else {"F": 0.70, "I": 0.80, "AC": 0.85}
    cog_min = gate_cfg.cognitiveAggregateMin if gate_cfg else 0.75
    gate = check_readiness_gate(s, scenario.tier, tier_thresholds, cog_min)

    existing = (
        await session.execute(select(Scorecard).where(Scorecard.runId == run.id))
    ).scalar_one_or_none()
    card = existing or Scorecard(runId=run.id)

    card.p1Correctness = s.p1_correctness
    card.p2Compliance = s.p2_compliance
    card.p3ProcessFidelity = s.p3_process_fidelity
    card.p4TimeToResolution = s.p4_time_to_resolution
    card.p5Escalation = s.p5_escalation
    card.p6DocQuality = s.p6_doc_quality
    card.p7CustomerExperience = s.p7_customer_experience
    card.p8CostDiscipline = s.p8_cost_discipline
    card.c1BreathCoherence = s.c1_breath_coherence
    card.c2SoulStability = s.c2_soul_stability
    card.c3FotPressureManagement = s.c3_fot_pressure_management
    card.c4ArcNarrativeCoherence = s.c4_arc_narrative_coherence
    card.c5EchoRegretLoad = s.c5_echo_regret_load
    card.c6HfmDriveBalance = s.c6_hfm_drive_balance
    card.c7AmeReputationTrajectory = s.c7_ame_reputation_trajectory
    card.cognitiveAggregate = s.cognitive_aggregate
    card.readinessGatePassed = gate.passed
    card.autoFailReason = gate.auto_fail_reason
    card.turnAnnotations = s.turn_annotations
    card.remediationRecs = s.remediation_recs

    if existing is None:
        session.add(card)
    await session.commit()
    await session.refresh(card)
    return card

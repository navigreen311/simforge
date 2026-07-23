"""Runs router (blueprint §C.3.6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import get_village_reader, require_role
from src.models.agent import Agent
from src.models.pack import Pack, Scenario
from src.models.run import Run, TraceEvent
from src.models.scorecard import Scorecard
from src.schemas.run import (
    RunList,
    RunSummary,
    TraceEventOut,
    TraceResponse,
    TranscriptResponse,
    TranscriptTurn,
)
from src.schemas.scorecard import ScorecardResponse
from src.services.village.reader import VillageReader

router = APIRouter()


async def _summarize(session: AsyncSession, run: Run) -> RunSummary:
    scenario = (
        await session.execute(select(Scenario).where(Scenario.id == run.scenarioId))
    ).scalar_one()
    agent = (await session.execute(select(Agent).where(Agent.id == run.agentId))).scalar_one()
    pack = (await session.execute(select(Pack).where(Pack.id == run.packId))).scalar_one()
    return RunSummary(
        run_id=run.runId,
        scenario_id=scenario.scenarioId,
        agent_village_id=agent.villageAgentId,
        pack_id=pack.packId,
        status=run.status,
        outcome=run.outcome,
        execution_mode=run.executionMode,
        blind_mode=run.blindMode,
        started_at=run.startedAt,
        ended_at=run.endedAt,
        latency_ms=run.latencyMs,
        tokens_used=run.tokensUsed,
        cost_usd=run.costUsd,
    )


async def _get_run_or_404(session: AsyncSession, run_id: str) -> Run:
    run = (await session.execute(select(Run).where(Run.runId == run_id))).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _apply_run_filters(
    stmt,  # noqa: ANN001 — a SQLAlchemy Select whose type is verbose to spell
    *,
    run_status: str | None,
    tier: str | None,
    execution_mode: str | None,
    blind: bool | None,
    agent: str | None,
    pack: str | None,
    from_date: str | None,
    to_date: str | None,
):  # noqa: ANN201
    """Apply the optional Runs filters to a base select. All params are backward-compatible."""
    if run_status:
        stmt = stmt.where(Run.status == run_status)
    if execution_mode:
        stmt = stmt.where(Run.executionMode == execution_mode)
    if blind is not None:
        stmt = stmt.where(Run.blindMode == blind)
    if tier:
        stmt = stmt.where(Run.scenarioId.in_(select(Scenario.id).where(Scenario.tier == tier)))
    if agent:
        stmt = stmt.where(Run.agentId.in_(select(Agent.id).where(Agent.villageAgentId == agent)))
    if pack:
        stmt = stmt.where(Run.packId.in_(select(Pack.id).where(Pack.packId == pack)))
    if from_date:
        stmt = stmt.where(Run.startedAt >= from_date)
    if to_date:
        stmt = stmt.where(Run.startedAt <= to_date)
    return stmt


@router.get("/", response_model=RunList, dependencies=[Depends(require_role("viewer"))])
async def list_runs(
    session: AsyncSession = Depends(get_session),
    run_status: str | None = Query(default=None, alias="status"),
    tier: str | None = Query(default=None),
    execution_mode: str | None = Query(default=None),
    blind: bool | None = Query(default=None),
    agent: str | None = Query(default=None, description="Filter by tested agent villageAgentId"),
    pack: str | None = Query(default=None, description="Filter by pack packId"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> RunList:
    filters = {
        "run_status": run_status,
        "tier": tier,
        "execution_mode": execution_mode,
        "blind": blind,
        "agent": agent,
        "pack": pack,
        "from_date": from_date,
        "to_date": to_date,
    }
    count_stmt = _apply_run_filters(select(func.count()).select_from(Run), **filters)
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = _apply_run_filters(select(Run), **filters)
    rows = (
        (await session.execute(stmt.order_by(Run.startedAt.desc()).offset(offset).limit(limit)))
        .scalars()
        .all()
    )
    return RunList(items=[await _summarize(session, r) for r in rows], total=total)


@router.get("/counts", dependencies=[Depends(require_role("viewer"))])
async def run_counts(
    session: AsyncSession = Depends(get_session),
    run_status: str | None = Query(default=None, alias="status"),
    tier: str | None = Query(default=None),
    execution_mode: str | None = Query(default=None),
    blind: bool | None = Query(default=None),
    agent: str | None = Query(default=None),
    pack: str | None = Query(default=None),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
) -> dict:
    """Total + per-status + per-outcome counts for the (optionally filtered) run set."""
    filters = {
        "run_status": run_status,
        "tier": tier,
        "execution_mode": execution_mode,
        "blind": blind,
        "agent": agent,
        "pack": pack,
        "from_date": from_date,
        "to_date": to_date,
    }
    by_status = dict(
        (
            await session.execute(
                _apply_run_filters(
                    select(Run.status, func.count()).select_from(Run), **filters
                ).group_by(Run.status)
            )
        ).all()
    )
    total = sum(by_status.values())
    return {
        "total": total,
        "by_status": by_status,
        "passed": by_status.get("passed", 0),
        "failed": by_status.get("failed", 0),
        "errored": by_status.get("errored", 0),
    }


@router.get("/{run_id}", response_model=RunSummary, dependencies=[Depends(require_role("viewer"))])
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)) -> RunSummary:
    run = await _get_run_or_404(session, run_id)
    return await _summarize(session, run)


@router.get(
    "/{run_id}/transcript",
    response_model=TranscriptResponse,
    dependencies=[Depends(require_role("viewer"))],
)
async def get_transcript(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> TranscriptResponse:
    run = await _get_run_or_404(session, run_id)
    turns = [TranscriptTurn(**t) for t in (run.transcript or [])]
    return TranscriptResponse(run_id=run.runId, turns=turns)


@router.get(
    "/{run_id}/scorecard",
    response_model=ScorecardResponse,
    dependencies=[Depends(require_role("viewer"))],
)
async def get_scorecard(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> ScorecardResponse:
    run = await _get_run_or_404(session, run_id)
    card = (
        await session.execute(select(Scorecard).where(Scorecard.runId == run.id))
    ).scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No scorecard yet")
    return ScorecardResponse(
        run_id=run.runId,
        p1_correctness=card.p1Correctness,
        p2_compliance=card.p2Compliance,
        p3_process_fidelity=card.p3ProcessFidelity,
        p4_time_to_resolution=card.p4TimeToResolution,
        p5_escalation=card.p5Escalation,
        p6_doc_quality=card.p6DocQuality,
        p7_customer_experience=card.p7CustomerExperience,
        p8_cost_discipline=card.p8CostDiscipline,
        c1_breath_coherence=card.c1BreathCoherence,
        c2_soul_stability=card.c2SoulStability,
        c3_fot_pressure_management=card.c3FotPressureManagement,
        c4_arc_narrative_coherence=card.c4ArcNarrativeCoherence,
        c5_echo_regret_load=card.c5EchoRegretLoad,
        c6_hfm_drive_balance=card.c6HfmDriveBalance,
        c7_ame_reputation_trajectory=card.c7AmeReputationTrajectory,
        cognitive_aggregate=card.cognitiveAggregate,
        readiness_gate_passed=card.readinessGatePassed,
        auto_fail_reason=card.autoFailReason,
        turn_annotations=card.turnAnnotations or [],
        remediation_recs=card.remediationRecs,
    )


@router.post("/{run_id}/replay", dependencies=[Depends(require_role("prompt_engineer"))])
async def replay_run_endpoint(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    reader: VillageReader = Depends(get_village_reader),
) -> dict:
    """Time-travel replay (ADR-0032): re-execute this run's scenario and diff against the original.

    Deterministic (stub) replays reproduce the run bit-for-bit (`deterministic: true`, empty diff);
    divergence under a real LLM provider is surfaced as scorecard/transcript diffs. Always sandboxed
    — never re-commits integrated side effects.
    """
    from src.services.replay import replay_run

    try:
        comparison = await replay_run(session, run_id, reader)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return comparison.as_dict()


@router.get(
    "/{run_id}/trace",
    response_model=TraceResponse,
    dependencies=[Depends(require_role("viewer"))],
)
async def get_trace(run_id: str, session: AsyncSession = Depends(get_session)) -> TraceResponse:
    run = await _get_run_or_404(session, run_id)
    events = (
        (
            await session.execute(
                select(TraceEvent).where(TraceEvent.runId == run.id).order_by(TraceEvent.timestamp)
            )
        )
        .scalars()
        .all()
    )
    return TraceResponse(
        run_id=run.runId,
        events=[
            TraceEventOut(
                timestamp=e.timestamp,
                event_type=e.eventType,
                phase=e.phase,
                turn_number=e.turnNumber,
                payload=e.payload,
            )
            for e in events
        ],
    )

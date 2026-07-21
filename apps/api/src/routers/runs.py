"""Runs router (blueprint §C.3.6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.agent import Agent
from src.models.pack import Pack, Scenario
from src.models.run import Run, TraceEvent
from src.schemas.run import (
    RunList,
    RunSummary,
    TraceEventOut,
    TraceResponse,
    TranscriptResponse,
    TranscriptTurn,
)

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


@router.get("/", response_model=RunList, dependencies=[Depends(require_role("viewer"))])
async def list_runs(
    session: AsyncSession = Depends(get_session),
    run_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
) -> RunList:
    stmt = select(Run)
    count_stmt = select(func.count()).select_from(Run)
    if run_status:
        stmt = stmt.where(Run.status == run_status)
        count_stmt = count_stmt.where(Run.status == run_status)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.order_by(Run.startedAt.desc()).limit(limit))).scalars().all()
    return RunList(items=[await _summarize(session, r) for r in rows], total=total)


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

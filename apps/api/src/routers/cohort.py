"""Cognitive canary + cohort analytics router (ADR-0034)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import get_village_reader, require_role
from src.models.cognitive_snapshot import CognitiveSnapshot
from src.services.cognitive import (
    capture_daily_snapshots,
    cohort_analytics,
    snapshot_history,
)
from src.services.village.reader import VillageReader

router = APIRouter()


@router.get("/snapshots/status", dependencies=[Depends(require_role("viewer"))])
async def snapshots_status(session: AsyncSession = Depends(get_session)) -> dict:
    """Whether historical snapshots exist to compute drift (derived; drift needs ≥2 dates)."""
    dates = (
        await session.execute(select(func.count(func.distinct(CognitiveSnapshot.date))))
    ).scalar_one()
    total = (
        await session.execute(select(func.count()).select_from(CognitiveSnapshot))
    ).scalar_one()
    latest = (await session.execute(select(func.max(CognitiveSnapshot.date)))).scalar_one()
    return {
        "snapshot_dates": dates,
        "total_snapshots": total,
        "latest_date": latest.isoformat() if latest else None,
        "drift_available": dates >= 2,
    }


@router.post("/snapshots", dependencies=[Depends(require_role("compliance_analyst"))])
async def run_daily_canary(
    session: AsyncSession = Depends(get_session),
    reader: VillageReader = Depends(get_village_reader),
) -> dict:
    """Capture today's cognitive snapshot for every agent (idempotent per day)."""
    return await capture_daily_snapshots(session, reader)


@router.get(
    "/agent/{agent_village_id}/cognitive-history",
    dependencies=[Depends(require_role("viewer"))],
)
async def cognitive_history(
    agent_village_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    """An agent's cognitive snapshots over time (drift magnitude + per-signal deltas)."""
    try:
        return await snapshot_history(session, agent_village_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/department/{department_key}/analytics",
    dependencies=[Depends(require_role("viewer"))],
)
async def department_analytics(
    department_key: str, session: AsyncSession = Depends(get_session)
) -> dict:
    """CohortHeatmap (agents × cognitive dims) + per-agent aggregate percentile for a department."""
    try:
        return await cohort_analytics(session, department_key)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

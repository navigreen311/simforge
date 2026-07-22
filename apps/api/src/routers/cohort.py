"""Cognitive canary + cohort analytics router (ADR-0034)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import get_village_reader, require_role
from src.services.cognitive import (
    capture_daily_snapshots,
    cohort_analytics,
    snapshot_history,
)
from src.services.village.reader import VillageReader

router = APIRouter()


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

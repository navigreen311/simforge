"""Scenarios router (blueprint §C.3.5). Phase 3: list + detail. `run` endpoints land in Phase 4."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.pack import Pack, Scenario
from src.schemas.pack import ScenarioSummary

router = APIRouter()


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def list_scenarios(
    session: AsyncSession = Depends(get_session),
    pack_id: str | None = Query(default=None, description="Filter by Pack packId"),
    tier: str | None = Query(default=None),
) -> dict:
    stmt = select(Scenario)
    count_stmt = select(func.count()).select_from(Scenario)
    if pack_id:
        stmt = stmt.join(Pack, Scenario.packId == Pack.id).where(Pack.packId == pack_id)
        count_stmt = count_stmt.join(Pack, Scenario.packId == Pack.id).where(Pack.packId == pack_id)
    if tier:
        stmt = stmt.where(Scenario.tier == tier)
        count_stmt = count_stmt.where(Scenario.tier == tier)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.order_by(Scenario.scenarioId))).scalars().all()
    return {
        "items": [ScenarioSummary.model_validate(s).model_dump() for s in rows],
        "total": total,
    }


@router.get(
    "/{scenario_id}",
    response_model=ScenarioSummary,
    dependencies=[Depends(require_role("viewer"))],
)
async def get_scenario(
    scenario_id: str, session: AsyncSession = Depends(get_session)
) -> ScenarioSummary:
    scen = (
        await session.execute(select(Scenario).where(Scenario.scenarioId == scenario_id))
    ).scalar_one_or_none()
    if scen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return ScenarioSummary.model_validate(scen)

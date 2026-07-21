"""Agents router (blueprint §C.3.2).

Phase 1: list + detail. Autonomy/CCB endpoints land in later phases.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.agent import Agent
from src.schemas.agent import AgentList, AgentSummary

router = APIRouter()


@router.get("/", response_model=AgentList, dependencies=[Depends(require_role("viewer"))])
async def list_agents(
    session: AsyncSession = Depends(get_session),
    department_id: str | None = Query(default=None),
    autonomy_level: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> AgentList:
    stmt = select(Agent)
    count_stmt = select(func.count()).select_from(Agent)
    if department_id:
        stmt = stmt.where(Agent.departmentId == department_id)
        count_stmt = count_stmt.where(Agent.departmentId == department_id)
    if autonomy_level:
        stmt = stmt.where(Agent.currentAutonomyLevel == autonomy_level)
        count_stmt = count_stmt.where(Agent.currentAutonomyLevel == autonomy_level)

    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Agent.name).offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(stmt)).scalars().all()

    return AgentList(
        items=[AgentSummary.model_validate(a) for a in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{village_agent_id}",
    response_model=AgentSummary,
    dependencies=[Depends(require_role("viewer"))],
)
async def get_agent(
    village_agent_id: str, session: AsyncSession = Depends(get_session)
) -> AgentSummary:
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == village_agent_id))
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return AgentSummary.model_validate(agent)

"""Agents router (blueprint §C.3.2).

Phase 1: list + detail. Autonomy/CCB endpoints land in later phases.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import get_village_reader, require_role
from src.models.agent import Agent
from src.models.cert import AutonomyEvent
from src.schemas.agent import (
    AgentList,
    AgentsLegendOut,
    AgentSummary,
    FlagInfoOut,
    LadderLevelOut,
)
from src.schemas.ccb import CCBCaptureRequest, CCBResponse
from src.services.cert.autonomy_ladder import (
    FLOOR,
    LEVELS,
    demote,
    ladder_levels,
    record_transition,
)
from src.services.village.ccb_store import (
    capture_ccb,
    get_latest_ccb,
    model_to_response_dict,
)
from src.services.village.reader import VillageReader

router = APIRouter()

# Plain-language flag vocabulary. Neither flag has a FORMAL in-app policy definition (only blueprint
# mentions), so `defined=False` and the descriptions cite the blueprint rather than assert a policy.
_FLAG_CATALOG: list[dict] = [
    {
        "key": "gardner",
        "label": "Gardner",
        "meaning": "Marks the executive 'Gardner' agent — per the blueprint, the only Village "
        "agent with phone capability. No formal in-app policy definition.",
        "defined": False,
    },
    {
        "key": "l10",
        "label": "L10",
        "meaning": "'Level 10' cognitive layer enabled — per the blueprint, Gardner-only and "
        "skipped in v1. Distinct from the L1–L5 autonomy ladder. No formal in-app definition.",
        "defined": False,
    },
]


@router.get(
    "/legend", response_model=AgentsLegendOut, dependencies=[Depends(require_role("viewer"))]
)
async def agents_legend() -> AgentsLegendOut:
    """The autonomy ladder + flag vocabulary in plain language (drives the page legends)."""
    return AgentsLegendOut(
        floor=FLOOR,
        levels=[LadderLevelOut(**lvl) for lvl in ladder_levels()],
        flags=[FlagInfoOut(**f) for f in _FLAG_CATALOG],
    )


@router.get("/", response_model=AgentList, dependencies=[Depends(require_role("viewer"))])
async def list_agents(
    session: AsyncSession = Depends(get_session),
    department_id: str | None = Query(default=None),
    autonomy_level: str | None = Query(default=None),
    search: str | None = Query(default=None, description="Match name / villageAgentId / role"),
    gardner_flag: bool | None = Query(default=None),
    level10: bool | None = Query(default=None, alias="level10"),
    has_active_certs: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> AgentList:
    from src.models.cert import AgentCert

    def _apply(stmt):  # noqa: ANN001, ANN202
        if department_id:
            stmt = stmt.where(Agent.departmentId == department_id)
        if autonomy_level:
            stmt = stmt.where(Agent.currentAutonomyLevel == autonomy_level)
        if gardner_flag is not None:
            stmt = stmt.where(Agent.gardnerFlag == gardner_flag)
        if level10 is not None:
            stmt = stmt.where(Agent.level10Enabled == level10)
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                func.lower(Agent.name).like(like)
                | func.lower(Agent.villageAgentId).like(like)
                | func.lower(Agent.role).like(like)
            )
        if has_active_certs is not None:
            with_active = select(AgentCert.agentId).where(AgentCert.status == "active")
            stmt = (
                stmt.where(Agent.id.in_(with_active))
                if has_active_certs
                else stmt.where(Agent.id.not_in(with_active))
            )
        return stmt

    total = (await session.execute(_apply(select(func.count()).select_from(Agent)))).scalar_one()
    stmt = (
        _apply(select(Agent)).order_by(Agent.name).offset((page - 1) * page_size).limit(page_size)
    )
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


@router.post(
    "/{village_agent_id}/ccb/capture",
    response_model=CCBResponse,
    dependencies=[Depends(require_role("prompt_engineer"))],
)
async def capture_agent_ccb(
    village_agent_id: str,
    body: CCBCaptureRequest | None = None,
    session: AsyncSession = Depends(get_session),
    reader: VillageReader = Depends(get_village_reader),
) -> CCBResponse:
    """Compose a CCB from Village state and persist it (blueprint §C.7)."""
    from src.services.village.reader import VillageReaderError

    body = body or CCBCaptureRequest()
    phase = body.phase if body.phase in ("pre", "post") else "pre"
    try:
        row = await capture_ccb(session, reader, village_agent_id, phase)  # type: ignore[arg-type]
    except VillageReaderError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CCBResponse(**model_to_response_dict(row))


async def _get_agent_or_404(session: AsyncSession, village_agent_id: str) -> Agent:
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == village_agent_id))
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.get(
    "/{village_agent_id}/autonomy-history",
    dependencies=[Depends(require_role("viewer"))],
)
async def autonomy_history(
    village_agent_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    agent = await _get_agent_or_404(session, village_agent_id)
    events = (
        (
            await session.execute(
                select(AutonomyEvent)
                .where(AutonomyEvent.agentId == agent.id)
                .order_by(AutonomyEvent.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "current_level": agent.currentAutonomyLevel,
        "events": [
            {"from": e.fromLevel, "to": e.toLevel, "reason": e.reason, "by": e.triggeredBy}
            for e in events
        ],
    }


@router.post(
    "/{village_agent_id}/autonomy/promote",
    response_model=AgentSummary,
    dependencies=[Depends(require_role("admin"))],
)
async def promote_autonomy(
    village_agent_id: str, session: AsyncSession = Depends(get_session)
) -> AgentSummary:
    """Manual promotion by one level (Ivan-only, audited)."""
    agent = await _get_agent_or_404(session, village_agent_id)
    idx = LEVELS.index(agent.currentAutonomyLevel) if agent.currentAutonomyLevel in LEVELS else 0
    if idx >= len(LEVELS) - 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already at L5")
    await record_transition(session, agent, LEVELS[idx + 1], "manual_override", "admin")
    await session.commit()
    return AgentSummary.model_validate(agent)


@router.post(
    "/{village_agent_id}/autonomy/downgrade",
    response_model=AgentSummary,
    dependencies=[Depends(require_role("admin"))],
)
async def downgrade_autonomy(
    village_agent_id: str, session: AsyncSession = Depends(get_session)
) -> AgentSummary:
    """Manual downgrade by one level (Ivan-only, audited)."""
    agent = await _get_agent_or_404(session, village_agent_id)
    idx = LEVELS.index(agent.currentAutonomyLevel) if agent.currentAutonomyLevel in LEVELS else 0
    if idx <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already at L1")
    await demote(session, agent, LEVELS[idx - 1], "manual_override", "admin")
    await session.commit()
    return AgentSummary.model_validate(agent)


@router.get(
    "/{village_agent_id}/ccb/latest",
    response_model=CCBResponse,
    dependencies=[Depends(require_role("viewer"))],
)
async def latest_agent_ccb(
    village_agent_id: str,
    phase: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> CCBResponse:
    """Return the most recent persisted CCB for an agent (blueprint §C.3.2)."""
    row = await get_latest_ccb(session, village_agent_id, phase)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No CCB captured yet")
    return CCBResponse(**model_to_response_dict(row))

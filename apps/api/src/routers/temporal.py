"""Temporal Realism Engine router (v1.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.temporal_scenario import TemporalScenario
from src.services.temporal.engine import simulate

router = APIRouter()


class TemporalEvent(BaseModel):
    at_turn: int = Field(ge=0)
    kind: str = "delayed"
    description: str = ""


class TimeBomb(BaseModel):
    deadline_turn: int = Field(ge=0)
    defuse: str
    consequence: str = ""


class TemporalScenarioBody(BaseModel):
    name: str
    scenario_id: str | None = None
    events: list[TemporalEvent] = []
    time_bombs: list[TimeBomb] = []


class SimulateBody(BaseModel):
    events: list[TemporalEvent] = []
    time_bombs: list[TimeBomb] = []
    agent_turns: list[str] = []


def _out(t: TemporalScenario) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "scenario_id": t.scenarioId,
        "events": t.events,
        "time_bombs": t.timeBombs,
    }


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def list_temporal(session: AsyncSession = Depends(get_session)) -> dict:
    rows = (
        (
            await session.execute(
                select(TemporalScenario).order_by(TemporalScenario.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )
    return {"temporal_scenarios": [_out(t) for t in rows], "total": len(rows)}


@router.post("/", dependencies=[Depends(require_role("compliance_analyst"))])
async def create_temporal(
    body: TemporalScenarioBody, session: AsyncSession = Depends(get_session)
) -> dict:
    row = TemporalScenario(
        name=body.name,
        scenarioId=body.scenario_id,
        events=[e.model_dump() for e in body.events],
        timeBombs=[b.model_dump() for b in body.time_bombs],
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _out(row)


@router.post("/simulate", dependencies=[Depends(require_role("viewer"))])
async def simulate_adhoc(body: SimulateBody) -> dict:
    return simulate(
        [e.model_dump() for e in body.events],
        [b.model_dump() for b in body.time_bombs],
        body.agent_turns,
    )


@router.post("/{temporal_id}/simulate", dependencies=[Depends(require_role("viewer"))])
async def simulate_stored(
    temporal_id: str, agent_turns: list[str], session: AsyncSession = Depends(get_session)
) -> dict:
    row = (
        await session.execute(select(TemporalScenario).where(TemporalScenario.id == temporal_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TemporalScenario not found: {temporal_id}",
        )
    return simulate(list(row.events or []), list(row.timeBombs or []), agent_turns)

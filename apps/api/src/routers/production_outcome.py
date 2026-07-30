"""Production Outcome Correlation router (v1.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.production_outcome import ProductionOutcome
from src.services.correlation.production import correlate, record_outcome

router = APIRouter()


class OutcomeBody(BaseModel):
    agent_village_id: str
    forge_cap: str
    outcome_score: float = Field(ge=0.0, le=1.0)
    period: str = ""
    sample_size: int = 0
    source: str = "manual"
    notes: str | None = None
    recorded_by: str = "system"


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def list_outcomes(session: AsyncSession = Depends(get_session)) -> dict:
    rows = (
        (
            await session.execute(
                select(ProductionOutcome).order_by(ProductionOutcome.recordedAt.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "outcomes": [
            {
                "agent_village_id": r.agentVillageId,
                "forge_cap": r.forgeCap,
                "outcome_score": r.outcomeScore,
                "period": r.period,
                "sample_size": r.sampleSize,
                "source": r.source,
                "recorded_at": r.recordedAt.isoformat() if r.recordedAt else None,
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.get("/correlation", dependencies=[Depends(require_role("viewer"))])
async def correlation(session: AsyncSession = Depends(get_session)) -> dict:
    return await correlate(session)


@router.post("/", dependencies=[Depends(require_role("compliance_analyst"))])
async def record(body: OutcomeBody, session: AsyncSession = Depends(get_session)) -> dict:
    row = await record_outcome(
        session,
        agent_village_id=body.agent_village_id,
        forge_cap=body.forge_cap,
        outcome_score=body.outcome_score,
        period=body.period,
        sample_size=body.sample_size,
        source=body.source,
        notes=body.notes,
        recorded_by=body.recorded_by,
    )
    return {"id": row.id, "agent_village_id": row.agentVillageId, "forge_cap": row.forgeCap}

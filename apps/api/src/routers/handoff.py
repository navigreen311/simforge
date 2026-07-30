"""Multi-agent handoff integrity router (v1.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.handoff_test import HandoffTest
from src.services.handoff.integrity import evaluate

router = APIRouter()


class HandoffStep(BaseModel):
    from_agent: str
    to_agent: str
    provides: list[str] = []
    required: list[str] = []
    consent: bool = False


class HandoffTestBody(BaseModel):
    name: str
    scenario_id: str | None = None
    chain: list[HandoffStep] = []


def _to_engine(chain: list[HandoffStep]) -> list[dict]:
    return [
        {
            "from": s.from_agent,
            "to": s.to_agent,
            "provides": s.provides,
            "required": s.required,
            "consent": s.consent,
        }
        for s in chain
    ]


def _out(t: HandoffTest) -> dict:
    return {"id": t.id, "name": t.name, "scenario_id": t.scenarioId, "chain": t.chain}


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def list_tests(session: AsyncSession = Depends(get_session)) -> dict:
    rows = (
        (await session.execute(select(HandoffTest).order_by(HandoffTest.createdAt.desc())))
        .scalars()
        .all()
    )
    return {"handoff_tests": [_out(t) for t in rows], "total": len(rows)}


@router.post("/", dependencies=[Depends(require_role("compliance_analyst"))])
async def create_test(body: HandoffTestBody, session: AsyncSession = Depends(get_session)) -> dict:
    row = HandoffTest(name=body.name, scenarioId=body.scenario_id, chain=_to_engine(body.chain))
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _out(row)


@router.post("/evaluate", dependencies=[Depends(require_role("viewer"))])
async def evaluate_adhoc(body: HandoffTestBody) -> dict:
    return evaluate(_to_engine(body.chain))


@router.post("/{test_id}/evaluate", dependencies=[Depends(require_role("viewer"))])
async def evaluate_stored(test_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    row = (
        await session.execute(select(HandoffTest).where(HandoffTest.id == test_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"HandoffTest not found: {test_id}"
        )
    return evaluate(list(row.chain or []))

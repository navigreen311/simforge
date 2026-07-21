"""Agent training router — proposals + approval-gated promotion (ADR-0026)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.agent import Agent
from src.models.training import TrainingProposal
from src.services.training import analyze_run_for_training, approve_proposal, reject_proposal

router = APIRouter()


class ReviewRequest(BaseModel):
    reviewer: str = "ivan"


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agentId: str
    runId: str | None
    weakDims: list[str]
    currentPromptVersion: str
    proposedPromptVersion: str
    rationale: str
    proposedRefinement: str
    status: str
    autoApplied: bool
    reviewedBy: str | None
    reviewedAt: datetime | None
    createdAt: datetime


@router.post(
    "/proposals/from-run/{run_id}",
    dependencies=[Depends(require_role("prompt_engineer"))],
)
async def propose_from_run(run_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Generate a training proposal from a run's weak scorecard (none if the run scored well)."""
    proposal = await analyze_run_for_training(session, run_id)
    if proposal is None:
        return {"proposal": None, "reason": "no weak LLM-judge dimension on this run"}
    return {"proposal": ProposalOut.model_validate(proposal).model_dump(mode="json")}


@router.get(
    "/proposals", response_model=list[ProposalOut], dependencies=[Depends(require_role("viewer"))]
)
async def list_proposals(
    agent_village_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> list[ProposalOut]:
    stmt = select(TrainingProposal).order_by(TrainingProposal.createdAt.desc())
    if agent_village_id:
        agent = (
            await session.execute(select(Agent).where(Agent.villageAgentId == agent_village_id))
        ).scalar_one_or_none()
        stmt = stmt.where(TrainingProposal.agentId == (agent.id if agent else "none"))
    if status_filter:
        stmt = stmt.where(TrainingProposal.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return [ProposalOut.model_validate(r) for r in rows]


@router.post("/proposals/{proposal_id}/approve", dependencies=[Depends(require_role("admin"))])
async def approve(
    proposal_id: str, body: ReviewRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    """Approve → promote the prompt version + suspend certs pinned to the old version (re-cert)."""
    try:
        return await approve_proposal(session, proposal_id, body.reviewer)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/proposals/{proposal_id}/reject", dependencies=[Depends(require_role("admin"))])
async def reject(
    proposal_id: str, body: ReviewRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        return await reject_proposal(session, proposal_id, body.reviewer)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

"""Scenario Truth Review Gate router (v1.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_session
from src.deps import require_role
from src.models.scenario_truth_review import TRUTH_CHECKLIST, ScenarioTruthReview
from src.services.scenario.truth_review import (
    TruthReviewError,
    get_review,
    list_unreviewed,
    submit_review,
)

router = APIRouter()


class ReviewBody(BaseModel):
    reviewer: str
    checklist: dict[str, bool]
    notes: str | None = None


def _out(r: ScenarioTruthReview) -> dict:
    return {
        "scenario_id": r.scenarioId,
        "status": r.status,
        "checklist": r.checklist,
        "reviewer": r.reviewer,
        "notes": r.notes,
        "reviewed_at": r.reviewedAt.isoformat() if r.reviewedAt else None,
    }


@router.get("/checklist", dependencies=[Depends(require_role("viewer"))])
async def checklist_dimensions() -> dict:
    return {"dimensions": list(TRUTH_CHECKLIST), "enforced": settings.truth_gate_enforce}


@router.get("/unreviewed", dependencies=[Depends(require_role("viewer"))])
async def unreviewed(session: AsyncSession = Depends(get_session)) -> dict:
    ids = await list_unreviewed(session)
    return {"scenario_ids": ids, "total": len(ids)}


@router.get("/{scenario_id}", dependencies=[Depends(require_role("viewer"))])
async def review_for(scenario_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    review = await get_review(session, scenario_id)
    if review is None:
        return {"scenario_id": scenario_id, "status": "unreviewed", "checklist": {}}
    return _out(review)


@router.post("/{scenario_id}", dependencies=[Depends(require_role("compliance_analyst"))])
async def submit(
    scenario_id: str, body: ReviewBody, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        review = await submit_review(
            session,
            scenario_id=scenario_id,
            reviewer=body.reviewer,
            checklist=body.checklist,
            notes=body.notes,
        )
    except TruthReviewError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _out(review)

"""Meta-Eval router — evaluate the evaluator (ADR-0027)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.meta_eval_intent import INTENTS, MetaEvalIntent
from src.services.meta_eval import meta_eval_report

router = APIRouter()


@router.get("/report", dependencies=[Depends(require_role("viewer"))])
async def report(
    pack_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Per-dimension stats + discrimination + verdicts over the scorecard population."""
    return await meta_eval_report(session, pack_id=pack_id)


@router.get("/intents", dependencies=[Depends(require_role("viewer"))])
async def list_intents(session: AsyncSession = Depends(get_session)) -> dict:
    """The owner's advisory remediation intents, keyed by dimension. Never affects scoring."""
    rows = (await session.execute(select(MetaEvalIntent))).scalars().all()
    return {
        "intents": {
            r.dim: {"intent": r.intent, "note": r.note, "updated_by": r.updatedBy} for r in rows
        }
    }


class IntentBody(BaseModel):
    intent: str
    note: str = ""
    actor: str = "owner"


@router.put("/intents/{dim}", dependencies=[Depends(require_role("compliance_analyst"))])
async def set_intent(
    dim: str, body: IntentBody, session: AsyncSession = Depends(get_session)
) -> dict:
    """Record (or update) the owner's advisory remediation intent for a dimension.

    ADVISORY ONLY — a triage note. It never changes a score, a weight, or a certification."""
    if body.intent not in INTENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"intent must be one of {INTENTS}",
        )
    row = (
        await session.execute(select(MetaEvalIntent).where(MetaEvalIntent.dim == dim))
    ).scalar_one_or_none()
    if row is None:
        row = MetaEvalIntent(dim=dim, intent=body.intent, note=body.note, updatedBy=body.actor)
        session.add(row)
    else:
        row.intent = body.intent
        row.note = body.note
        row.updatedBy = body.actor
    await session.commit()
    return {"dim": dim, "intent": row.intent, "note": row.note, "updated_by": row.updatedBy}

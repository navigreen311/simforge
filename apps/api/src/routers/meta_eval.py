"""Meta-Eval router — evaluate the evaluator (ADR-0027)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.meta_eval import meta_eval_report

router = APIRouter()


@router.get("/report", dependencies=[Depends(require_role("viewer"))])
async def report(
    pack_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Per-dimension stats + discrimination + flags over the scorecard population."""
    return await meta_eval_report(session, pack_id=pack_id)

"""Coverage Optimizer router (v1.2) — ranked scenario-authoring worklist."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.coverage.optimizer import optimize

router = APIRouter()


@router.get("/recommendations", dependencies=[Depends(require_role("viewer"))])
async def recommendations(
    min_per_cell: int = Query(default=3, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await optimize(session, min_per_cell=min_per_cell)

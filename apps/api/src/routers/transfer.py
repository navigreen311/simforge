"""Cross-Pack Learning Transfer router (v1.2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.transfer.cross_pack import transfer_opportunities

router = APIRouter()


@router.get("/opportunities", dependencies=[Depends(require_role("viewer"))])
async def opportunities(
    min_scenarios: int = Query(default=3, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await transfer_opportunities(session, min_scenarios=min_scenarios)

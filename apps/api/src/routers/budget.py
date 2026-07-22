"""Budget router — monthly cost-cap status (ADR-0039)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.budget import budget_status

router = APIRouter()


@router.get("/status", dependencies=[Depends(require_role("viewer"))])
async def status(session: AsyncSession = Depends(get_session)) -> dict:
    """This month's spend / cap / remaining for sandbox and integrated runs."""
    return await budget_status(session)

"""Stakeholder Communication router (v1.2) — executive brief."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.comms.stakeholder import portfolio_brief

router = APIRouter()


@router.get("/brief", dependencies=[Depends(require_role("viewer"))])
async def brief(session: AsyncSession = Depends(get_session)) -> dict:
    return await portfolio_brief(session)

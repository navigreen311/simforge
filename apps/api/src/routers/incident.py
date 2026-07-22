"""Incident Command router — the on-call operational view (ADR-0040)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.incident import incident_report

router = APIRouter()


@router.get("/status", dependencies=[Depends(require_role("viewer"))])
async def status(session: AsyncSession = Depends(get_session)) -> dict:
    """Active incidents + blast radius + safe-mode + budget — derived from live signals."""
    return await incident_report(session)

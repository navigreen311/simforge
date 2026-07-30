"""Regression router — detect scenario flips + auto-suspend affected certs (§9.2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.evaluation.regression_sweep import find_and_suspend_regressions

router = APIRouter()


@router.get("/status", dependencies=[Depends(require_role("viewer"))])
async def regression_status(session: AsyncSession = Depends(get_session)) -> dict:
    """Dry-run regression sweep over existing runs — reports flips without suspending."""
    report = await find_and_suspend_regressions(session, suspend=False)
    return report.as_dict()


@router.post("/sweep", dependencies=[Depends(require_role("admin"))])
async def regression_sweep(session: AsyncSession = Depends(get_session)) -> dict:
    """Run the sweep and auto-suspend certs on verified flips (does not re-run scenarios)."""
    report = await find_and_suspend_regressions(session, suspend=True)
    return report.as_dict()

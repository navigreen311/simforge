"""Drift Canary router — scan certs for Forge version drift (ADR-0017)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.drift import scan_forge_drift

router = APIRouter()


@router.get("/status", dependencies=[Depends(require_role("viewer"))])
async def drift_status(session: AsyncSession = Depends(get_session)) -> dict:
    """Dry-run drift scan — report drift against pinned Forge versions without suspending."""
    return await scan_forge_drift(session, actor="drift-status", suspend=False)


@router.post("/scan", dependencies=[Depends(require_role("admin"))])
async def drift_scan(session: AsyncSession = Depends(get_session)) -> dict:
    """Scan active certs and auto-suspend any whose pinned Forge version has drifted."""
    return await scan_forge_drift(session, actor="drift-canary", suspend=True)

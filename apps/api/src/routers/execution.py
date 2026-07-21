"""Integrated-execution router — the audit ledger + revert (ADR-0025)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_session
from src.deps import require_role
from src.services.execution import integrated_actions_for_run, revert_integrated_action

router = APIRouter()


class RevertRequest(BaseModel):
    actor: str = "admin"


@router.get("/status", dependencies=[Depends(require_role("viewer"))])
async def integrated_status() -> dict:
    """Whether integrated execution is enabled on this deployment (default off)."""
    return {"integrated_execution_enabled": settings.integrated_execution_enabled}


@router.get("/run/{run_id}/actions", dependencies=[Depends(require_role("viewer"))])
async def run_actions(run_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """The integrated-action ledger for a run (applied / blocked / reverted, with PDP reasons)."""
    ledger = await integrated_actions_for_run(session, run_id)
    return {"run_id": run_id, "actions": ledger}


@router.post(
    "/run/{run_id}/actions/{action_id}/revert",
    dependencies=[Depends(require_role("admin"))],
)
async def revert_action(
    run_id: str,
    action_id: str,
    body: RevertRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Reverse an applied integrated action with a compensating ledger entry."""
    try:
        return await revert_integrated_action(session, run_id, action_id, body.actor)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

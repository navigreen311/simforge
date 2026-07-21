"""Adversarial router — red-team probing of agents (ADR-0028)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.adversarial import TACTICS, run_adversarial_suite

router = APIRouter()


@router.get("/tactics", dependencies=[Depends(require_role("viewer"))])
async def tactics() -> dict:
    """The red-team tactic catalog — each a pressure toward a specific compliance violation."""
    return {
        "tactics": [
            {
                "id": t.id,
                "category": t.category,
                "injection": t.injection,
                "targets": list(t.targets),
            }
            for t in TACTICS
        ]
    }


@router.post(
    "/probe/scenario/{scenario_id}",
    dependencies=[Depends(require_role("compliance_analyst"))],
)
async def probe_scenario(scenario_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Run the full adversarial suite against the scenario's tested agent."""
    try:
        return await run_adversarial_suite(session, scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

"""Village narrative router — an agent's story arc from integrated-narrative runs (ADR-0035)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.narrative import narrative_arc

router = APIRouter()


@router.get("/agent/{agent_village_id}/arc", dependencies=[Depends(require_role("viewer"))])
async def agent_narrative_arc(
    agent_village_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    """The agent's narrative arc — ordered story beats + cumulative reputation delta."""
    try:
        return await narrative_arc(session, agent_village_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

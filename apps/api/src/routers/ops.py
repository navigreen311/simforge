"""Human Operating Model router (§11.8) — board, inboxes, ownership matrix, shift handoff."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.ops import handoff_report, ops_report, owners_matrix, role_inbox

router = APIRouter()


@router.get("/board", dependencies=[Depends(require_role("viewer"))])
async def board(session: AsyncSession = Depends(get_session)) -> dict:
    """The full ops board: every queue with open counts + SLA status (within/at_risk/breached)."""
    return await ops_report(session)


@router.get("/matrix", dependencies=[Depends(require_role("viewer"))])
async def matrix() -> dict:
    """The queue-ownership matrix (owner / backup / role / SLA)."""
    return {"matrix": owners_matrix()}


@router.get("/inbox/{role}", dependencies=[Depends(require_role("viewer"))])
async def inbox(role: str, session: AsyncSession = Depends(get_session)) -> dict:
    """A role's triage inbox — only the queues it owns."""
    return await role_inbox(session, role)


@router.get("/handoff", dependencies=[Depends(require_role("viewer"))])
async def handoff(session: AsyncSession = Depends(get_session)) -> dict:
    """Structured shift-handoff summary + SLA-breach read-back + active safe modes."""
    return await handoff_report(session)

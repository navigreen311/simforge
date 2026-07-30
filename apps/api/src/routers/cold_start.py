"""Cold-Start Playbook router (v1.2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.venture import Venture
from src.services.playbook.cold_start import all_playbooks, venture_playbook

router = APIRouter()


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def playbooks(session: AsyncSession = Depends(get_session)) -> dict:
    boards = await all_playbooks(session)
    return {"playbooks": boards, "total": len(boards)}


@router.get("/{venture_slug}", dependencies=[Depends(require_role("viewer"))])
async def playbook(venture_slug: str, session: AsyncSession = Depends(get_session)) -> dict:
    venture = (
        await session.execute(select(Venture).where(Venture.slug == venture_slug))
    ).scalar_one_or_none()
    if venture is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Venture not found: {venture_slug}"
        )
    return await venture_playbook(session, venture)

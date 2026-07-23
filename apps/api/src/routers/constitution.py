"""Constitution + amendments + safe-mode router (blueprint §C.3.13)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.governance import Constitution, ConstitutionalAmendment
from src.services.governance import (
    AmendmentError,
    get_current_constitution,
    propose_amendment,
    ratify_amendment,
    safe_mode,
    veto_amendment,
    withdraw_amendment,
)

router = APIRouter()


class ProposeAmendmentRequest(BaseModel):
    proposer_id: str
    diff_yaml: str
    cooling_days: int = 7


class SafeModeRequest(BaseModel):
    active: bool
    reason: str | None = None
    domains: list[str] = []


def _const_out(c: Constitution) -> dict:
    return {
        "version": c.version,
        "ratified_at": c.ratifiedAt,
        "ratified_by": c.ratifiedBy,
        "content_hash": c.contentHash,
        "superseded_by": c.supersededByVersion,
    }


@router.get("/current", dependencies=[Depends(require_role("viewer"))])
async def current(session: AsyncSession = Depends(get_session)) -> dict:
    c = await get_current_constitution(session)
    if c is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No constitution ratified"
        )
    return _const_out(c)


@router.get("/history", dependencies=[Depends(require_role("viewer"))])
async def history(session: AsyncSession = Depends(get_session)) -> dict:
    amendments = (
        (
            await session.execute(
                select(ConstitutionalAmendment).order_by(ConstitutionalAmendment.proposedAt.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "amendments": [
            {
                "amendment_id": a.amendmentId,
                "status": a.status,
                "proposed_by": a.proposedBy,
                "proposed_at": a.proposedAt,
                "cooling_ends_at": a.coolingPeriodEndsAt,
                "ratified_at": a.ratifiedAt,
                "ratified_by": a.ratifiedBy,
                "diff_yaml": a.diffYaml,  # the amendment body / change set
                "impact": a.impactAnalysis,
            }
            for a in amendments
        ]
    }


@router.get("/versions", dependencies=[Depends(require_role("viewer"))])
async def versions(session: AsyncSession = Depends(get_session)) -> dict:
    """All constitution versions with their active/superseded status (version history)."""
    rows = (
        (await session.execute(select(Constitution).order_by(Constitution.ratifiedAt.asc())))
        .scalars()
        .all()
    )
    return {"versions": [{**_const_out(c), "active": c.supersededByVersion is None} for c in rows]}


@router.get("/{version}", dependencies=[Depends(require_role("viewer"))])
async def get_version(version: str, session: AsyncSession = Depends(get_session)) -> dict:
    c = (
        await session.execute(select(Constitution).where(Constitution.version == version))
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return {**_const_out(c), "yaml": c.yamlContent}


@router.post("/amendments", dependencies=[Depends(require_role("admin"))])
async def propose(
    body: ProposeAmendmentRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        a = await propose_amendment(session, body.proposer_id, body.diff_yaml, body.cooling_days)
    except AmendmentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "amendment_id": a.amendmentId,
        "status": a.status,
        "cooling_ends_at": a.coolingPeriodEndsAt,
    }


@router.post("/amendments/{amendment_id}/withdraw", dependencies=[Depends(require_role("admin"))])
async def withdraw(amendment_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        a = await withdraw_amendment(session, amendment_id, "admin")
    except AmendmentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"amendment_id": a.amendmentId, "status": a.status}


@router.post("/amendments/{amendment_id}/veto", dependencies=[Depends(require_role("founder"))])
async def veto(amendment_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        a = await veto_amendment(session, amendment_id, "founder")
    except AmendmentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"amendment_id": a.amendmentId, "status": a.status}


@router.post("/amendments/{amendment_id}/ratify", dependencies=[Depends(require_role("admin"))])
async def ratify(amendment_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        return await ratify_amendment(session, amendment_id, "ivan")
    except AmendmentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/safe-mode/status", dependencies=[Depends(require_role("viewer"))])
async def safe_mode_status() -> dict:
    return safe_mode.status()


@router.post("/safe-mode", dependencies=[Depends(require_role("admin"))])
async def set_safe_mode(body: SafeModeRequest) -> dict:
    if body.active:
        safe_mode.activate("admin", body.reason or "manual", body.domains)
    else:
        safe_mode.deactivate()
    return safe_mode.status()

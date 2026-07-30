"""Dress Rehearsal router (§15) — entry/exit criteria + signed sign-offs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.dress_rehearsal import DressRehearsal
from src.services.rehearsal import (
    RehearsalError,
    check_entry_criteria,
    check_exit_criteria,
    run_exit,
    sign_off,
    start_rehearsal,
)

router = APIRouter()


class SignOffBody(BaseModel):
    role: str
    signer_id: str


def _out(r: DressRehearsal) -> dict:
    return {
        "id": r.id,
        "pack_id": r.packId,
        "status": r.status,
        "entry_results": r.entryResults,
        "exit_results": r.exitResults,
        "signoffs": r.signoffs,
    }


@router.get("/{pack_id}/entry-criteria", dependencies=[Depends(require_role("viewer"))])
async def entry_criteria(pack_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        return (await check_entry_criteria(session, pack_id)).as_dict()
    except RehearsalError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{pack_id}/exit-criteria", dependencies=[Depends(require_role("viewer"))])
async def exit_criteria(pack_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        return (await check_exit_criteria(session, pack_id)).as_dict()
    except RehearsalError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def list_rehearsals(session: AsyncSession = Depends(get_session)) -> dict:
    rows = (
        (await session.execute(select(DressRehearsal).order_by(DressRehearsal.createdAt.desc())))
        .scalars()
        .all()
    )
    return {"rehearsals": [_out(r) for r in rows]}


@router.post("/{pack_id}/start", dependencies=[Depends(require_role("compliance_analyst"))])
async def start(pack_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        return _out(await start_rehearsal(session, pack_id))
    except RehearsalError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{rehearsal_id}/exit", dependencies=[Depends(require_role("compliance_analyst"))])
async def exit_run(rehearsal_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        return _out(await run_exit(session, rehearsal_id))
    except RehearsalError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{rehearsal_id}/signoff", dependencies=[Depends(require_role("admin"))])
async def signoff(
    rehearsal_id: str, body: SignOffBody, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        return _out(await sign_off(session, rehearsal_id, role=body.role, signer_id=body.signer_id))
    except RehearsalError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

"""Jurisdiction Engine router — requirements + pack compliance coverage (ADR-0019)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.pack import Pack
from src.services.jurisdiction import (
    JURISDICTIONS,
    coverage_for_flags,
    resolve_requirements,
)
from src.services.jurisdiction.engine import UnknownJurisdictionError

router = APIRouter()


class CoverageRequest(BaseModel):
    declared_flags: list[str]
    phi_required: bool = False
    jurisdictions: list[str] | None = None  # inferred from flags if omitted


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def list_jurisdictions() -> dict:
    return {"jurisdictions": [asdict(j) for j in JURISDICTIONS.values()]}


@router.get("/{code}/requirements", dependencies=[Depends(require_role("viewer"))])
async def jurisdiction_requirements(code: str, phi_required: bool = True) -> dict:
    try:
        required = resolve_requirements([code], phi_required=phi_required)
    except UnknownJurisdictionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown jurisdiction: {exc}"
        ) from exc
    return {"jurisdiction": code.upper(), "phi_required": phi_required, "required_flags": required}


@router.post("/coverage", dependencies=[Depends(require_role("viewer"))])
async def coverage(body: CoverageRequest) -> dict:
    try:
        report = coverage_for_flags(
            body.declared_flags, phi_required=body.phi_required, jurisdictions=body.jurisdictions
        )
    except UnknownJurisdictionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown jurisdiction: {exc}"
        ) from exc
    return report.as_dict()


@router.get("/coverage/pack/{pack_id}", dependencies=[Depends(require_role("viewer"))])
async def pack_coverage(pack_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Infer a pack's jurisdictions from its declared compliance flags and report coverage gaps."""
    pack = (await session.execute(select(Pack).where(Pack.packId == pack_id))).scalar_one_or_none()
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pack not found")
    report = coverage_for_flags(list(pack.complianceFlags or []), phi_required=pack.phiRequired)
    return {"pack_id": pack_id, **report.as_dict()}

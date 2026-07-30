"""Forge parity SLA router (v1.1) — record + inspect sandbox-vs-production parity."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_session
from src.deps import require_role
from src.services.forge.parity import current_parity, parity_summary, record_parity

router = APIRouter()


class ParityBody(BaseModel):
    forge_cap: str
    parity_score: float = Field(ge=0.0, le=1.0)
    sample_size: int = 0
    method: str = "manual"
    notes: str | None = None
    measured_by: str = "system"


def _out(r) -> dict:  # noqa: ANN001
    return {
        "forge_cap": r.forgeCap,
        "parity_score": r.parityScore,
        "sla_threshold": r.slaThreshold,
        "unsafe_to_certify": r.unsafeToCertify,
        "sample_size": r.sampleSize,
        "method": r.method,
        "notes": r.notes,
        "measured_at": r.measuredAt.isoformat() if r.measuredAt else None,
        "measured_by": r.measuredBy,
    }


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def summary(session: AsyncSession = Depends(get_session)) -> dict:
    return {
        "sla_threshold": settings.parity_sla_threshold,
        "enforced": settings.parity_enforce,
        "forges": await parity_summary(session),
    }


@router.get("/{forge_cap}", dependencies=[Depends(require_role("viewer"))])
async def latest(forge_cap: str, session: AsyncSession = Depends(get_session)) -> dict:
    row = await current_parity(session, forge_cap)
    if row is None:
        return {"forge_cap": forge_cap, "measured": False, "unsafe_to_certify": False}
    return {"measured": True, **_out(row)}


@router.post("/", dependencies=[Depends(require_role("compliance_analyst"))])
async def record(body: ParityBody, session: AsyncSession = Depends(get_session)) -> dict:
    row = await record_parity(
        session,
        forge_cap=body.forge_cap,
        parity_score=body.parity_score,
        sample_size=body.sample_size,
        method=body.method,
        notes=body.notes,
        measured_by=body.measured_by,
    )
    return _out(row)

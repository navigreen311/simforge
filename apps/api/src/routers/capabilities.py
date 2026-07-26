"""Capability labels router — friendly names for Forge-capability ids (readable columns)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.cert import AgentCert
from src.services.capabilities import CAPABILITY_CATALOG, describe_capability

router = APIRouter()


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def capability_labels(session: AsyncSession = Depends(get_session)) -> dict:
    """Friendly {label, forge, description} for every capability referenced by a cert, plus the
    full known catalog. Deterministic; derived from the id (no LLM, no storage)."""
    cert_caps = set((await session.execute(select(AgentCert.forgeCap).distinct())).scalars().all())
    ids = cert_caps | set(CAPABILITY_CATALOG.keys())
    return {"capabilities": {cap: describe_capability(cap) for cap in sorted(ids)}}

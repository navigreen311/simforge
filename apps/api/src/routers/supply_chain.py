"""Supply-chain governance router (v1.2) — SBOM + dependency policy flags."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.deps import require_role
from src.services.supply_chain.sbom import generate_sbom

router = APIRouter()


@router.get("/sbom", dependencies=[Depends(require_role("viewer"))])
async def sbom() -> dict:
    return generate_sbom()

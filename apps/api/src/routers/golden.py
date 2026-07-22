"""Golden Benchmark router — the evaluator regression suite (ADR-0033)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import get_village_reader, require_role
from src.models.pack import Scenario
from src.services.golden import load_baseline, run_golden_suite
from src.services.village.reader import VillageReader

router = APIRouter()


@router.get("/scenarios", dependencies=[Depends(require_role("viewer"))])
async def golden_scenarios(session: AsyncSession = Depends(get_session)) -> dict:
    """The scenarios in the golden set (Scenario.isGolden)."""
    rows = (
        (await session.execute(select(Scenario).where(Scenario.isGolden.is_(True)))).scalars().all()
    )
    return {
        "scenarios": [
            {"scenario_id": s.scenarioId, "title": s.title, "tier": s.tier} for s in rows
        ],
        "total": len(rows),
    }


@router.get("/baseline", dependencies=[Depends(require_role("viewer"))])
async def golden_baseline() -> dict:
    """The committed expected baseline (outcome/gate/dims per golden scenario)."""
    return load_baseline()


@router.post("/run", dependencies=[Depends(require_role("compliance_analyst"))])
async def run_golden(
    session: AsyncSession = Depends(get_session),
    reader: VillageReader = Depends(get_village_reader),
) -> dict:
    """Run the golden suite and compare against the baseline → a regression report."""
    return await run_golden_suite(session, reader)

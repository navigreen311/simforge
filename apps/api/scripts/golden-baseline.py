"""Regenerate the Golden Benchmark baseline (ADR-0033).

Builds a hermetic in-memory DB, ingests the greenstone pack, runs every golden scenario, and writes
the expected outcome/gate/dims to apps/api/golden/baseline.json. Run this ONLY when a change to
golden behavior is intended — review the diff before committing.

    cd apps/api && python scripts/golden-baseline.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.models import Agent, Base, Department
from src.services.golden import DEFAULT_BASELINE_PATH, compute_golden
from src.services.packs.ingestion import ingest_pack
from src.services.village.reader import VillageReader

API_ROOT = Path(__file__).resolve().parents[1]
GREENSTONE = API_ROOT.parents[1] / "packs" / "greenstone" / "v1"
VILLAGE = API_ROOT / "tests" / "fixtures" / "village" / "VillageData"


async def main() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        dept = Department(villageKey="Sales", name="Sales", totalAgents=1)
        session.add(dept)
        await session.flush()
        session.add(
            Agent(
                villageAgentId="david_kim",
                name="David Kim",
                role="Account Executive",
                departmentId=dept.id,
                currentAutonomyLevel="L1",
            )
        )
        await session.commit()

        await ingest_pack(session, str(GREENSTONE))
        reader = VillageReader(village_data_path=VILLAGE)
        scenarios = await compute_golden(session, reader)

    baseline = {
        "note": "Golden Benchmark baseline (ADR-0033). Regenerate via scripts/golden-baseline.py "
        "only when a change to golden behavior is intended. p4_time_to_resolution is wall-clock-"
        "derived and compared with a coarse tolerance.",
        "provider": "stub",
        "scenarios": scenarios,
    }
    DEFAULT_BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_BASELINE_PATH.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(scenarios)} golden scenarios -> {DEFAULT_BASELINE_PATH}")


if __name__ == "__main__":
    asyncio.run(main())

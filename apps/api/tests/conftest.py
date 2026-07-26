"""Pytest fixtures — hermetic async SQLite DB + ASGI test client.

Phase 1 models (Agent, Department) use no Postgres-only column types, so SQLite is a fast,
Docker-free substrate for unit/integration tests. Phase 3+ (array/JSON columns) adds a
Postgres-backed integration path.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db import get_session
from src.deps import get_village_reader
from src.main import create_app
from src.models import Agent, Base, Department
from src.services.village.reader import VillageReader

VILLAGE_FIXTURE = Path(__file__).parent / "fixtures" / "village" / "VillageData"


@pytest.fixture
def village_reader() -> VillageReader:
    return VillageReader(village_data_path=VILLAGE_FIXTURE)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        # The Venture registry is the source of truth for the venture field, so seed the base
        # ventures before anything creates a Pack (Pack.ownerVenture → Venture.slug).
        from src.services.venture.registry import seed_base_ventures

        await seed_base_ventures(session)
        # Seed a small fixture set
        eng = Department(villageKey="Engineering", name="Engineering", totalAgents=2)
        rec = Department(villageKey="Recruitment", name="Recruitment", totalAgents=1)
        session.add_all([eng, rec])
        await session.flush()
        session.add_all(
            [
                Agent(
                    villageAgentId="taylor_zhang",
                    name="Taylor Zhang",
                    role="Senior Engineer",
                    departmentId=eng.id,
                    currentAutonomyLevel="L2",
                ),
                Agent(
                    villageAgentId="david_kim",
                    name="David Kim",
                    role="Account Executive",
                    departmentId=eng.id,
                    currentAutonomyLevel="L1",
                ),
                Agent(
                    villageAgentId="gardner",
                    name="Gardner",
                    role="Executive Agent",
                    departmentId=eng.id,
                    gardnerFlag=True,
                    level10Enabled=True,
                    currentAutonomyLevel="L1",
                ),
                Agent(
                    villageAgentId="jennifer_adams",
                    name="Jennifer Adams",
                    role="Recruiter",
                    departmentId=rec.id,
                    currentAutonomyLevel="L1",
                ),
            ]
        )
        await session.commit()
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_village_reader] = lambda: VillageReader(
        village_data_path=VILLAGE_FIXTURE
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

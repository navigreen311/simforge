"""Cold-Start Playbook (v1.2): venture signoff → v1-pack-ready milestones + SLA."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dress_rehearsal import DressRehearsal
from src.models.pack import Pack, Scenario
from src.models.scenario_truth_review import ScenarioTruthReview
from src.models.venture import Venture
from src.utils.time import utcnow

_N = [0]


def _venture(session: AsyncSession, *, slug: str, days_ago: int = 5) -> None:
    session.add(
        Venture(
            slug=slug,
            name=slug.title(),
            scenarioCode=slug[:2],
            status="in_development",
            createdAt=utcnow() - timedelta(days=days_ago),
        )
    )


def _pack(session: AsyncSession, *, venture: str, signed: bool = False) -> str:
    pid = f"dbid-{venture}"
    session.add(
        Pack(
            id=pid,
            packId=f"pack.{venture}.v1",
            name=venture,
            version="v1",
            ownerVenture=venture,
            ownerHuman="ivan",
            phiRequired=False,
            executionModeDefault="sandbox",
            narrativeModeDefault="protected",
            locale="en",
            rubricProfile="default",
            yamlPath="p.yml",
            yamlHash="h",
            signedBy="acquisitions_principal" if signed else None,
        )
    )
    return pid


def _scn(session: AsyncSession, *, pack_dbid: str) -> str:
    _N[0] += 1
    sid = f"scn.{_N[0]:04d}"
    session.add(
        Scenario(
            scenarioId=sid,
            packId=pack_dbid,
            title="t",
            tier="foundational",
            testedAgentVillageId="a",
            yamlPath="p.yml",
            yamlHash="h",
            sloSeconds=60,
            isGolden=False,
        )
    )
    return sid


async def test_fresh_venture_blocks_on_pack(client: AsyncClient, db_session: AsyncSession) -> None:
    _venture(db_session, slug="newco")
    await db_session.commit()
    board = (await client.get("/api/cold-start/newco")).json()
    assert board["ready"] is False
    assert board["blocking_step"] == "pack_created"
    assert board["progress"] == "1/6"
    assert board["sla_status"] == "within"


async def test_full_path_ready(client: AsyncClient, db_session: AsyncSession) -> None:
    _venture(db_session, slug="fullco")
    pid = _pack(db_session, venture="fullco", signed=True)
    sids = [_scn(db_session, pack_dbid=pid) for _ in range(3)]
    for sid in sids:
        db_session.add(
            ScenarioTruthReview(scenarioId=sid, status="approved", checklist={}, reviewer="ivan")
        )
    db_session.add(DressRehearsal(packId="pack.fullco.v1", status="signed"))
    await db_session.commit()

    board = (await client.get("/api/cold-start/fullco")).json()
    assert board["ready"] is True
    assert board["blocking_step"] is None
    assert board["progress"] == "6/6"
    assert board["sla_status"] == "met"


async def test_breached_sla(client: AsyncClient, db_session: AsyncSession) -> None:
    _venture(db_session, slug="slowco", days_ago=90)  # > 60-day target, not ready
    await db_session.commit()
    board = (await client.get("/api/cold-start/slowco")).json()
    assert board["sla_status"] == "breached"
    assert board["ready"] is False


async def test_list_and_404(client: AsyncClient, db_session: AsyncSession) -> None:
    _venture(db_session, slug="listco")
    await db_session.commit()
    listing = (await client.get("/api/cold-start/")).json()
    assert any(p["venture"] == "listco" for p in listing["playbooks"])
    missing = await client.get("/api/cold-start/nope")
    assert missing.status_code == 404

"""Cross-Pack Learning Transfer (v1.2): donor→recipient scenario-transfer opportunities."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pack import Pack, Scenario

_N = [0]


def _pack(session: AsyncSession, *, pack_id: str, venture: str = "greenstone") -> str:
    pid = f"dbid-{pack_id}"
    session.add(
        Pack(
            id=pid,
            packId=pack_id,
            name=pack_id,
            version="v1",
            ownerVenture=venture,
            ownerHuman="ivan",
            phiRequired=False,
            executionModeDefault="sandbox",
            narrativeModeDefault="protected",
            locale="en",
            rubricProfile="default",
            yamlPath=f"{pack_id}.yml",
            yamlHash="h",
        )
    )
    return pid


def _scn(session: AsyncSession, *, pack_dbid: str, cap: str) -> None:
    _N[0] += 1
    session.add(
        Scenario(
            scenarioId=f"scn.{_N[0]:04d}",
            packId=pack_dbid,
            title="t",
            tier="foundational",
            testedAgentVillageId="a",
            testedForgeCaps=[cap],
            yamlPath="p.yml",
            yamlHash="h",
            sloSeconds=60,
            isGolden=False,
        )
    )


async def test_donor_to_recipient_transfer(client: AsyncClient, db_session: AsyncSession) -> None:
    a = _pack(db_session, pack_id="pack.a")
    b = _pack(db_session, pack_id="pack.b", venture="careGrid")
    for _ in range(4):
        _scn(db_session, pack_dbid=a, cap="capital-forge")
    _scn(db_session, pack_dbid=b, cap="capital-forge")  # thin (1 < 3)
    await db_session.commit()

    res = (await client.get("/api/transfer/opportunities")).json()
    assert res["total_opportunities"] == 1
    t = res["transfers"][0]
    assert t["forge_cap"] == "capital-forge"
    assert t["donor_pack"] == "pack.a" and t["donor_scenarios"] == 4
    assert t["recipient_pack"] == "pack.b" and t["recipient_scenarios"] == 1
    assert t["suggested_transfer"] == 2
    assert t["cross_venture"] is True


async def test_no_transfer_when_single_pack(client: AsyncClient, db_session: AsyncSession) -> None:
    a = _pack(db_session, pack_id="pack.solo")
    for _ in range(4):
        _scn(db_session, pack_dbid=a, cap="vault-forge")
    await db_session.commit()
    res = (await client.get("/api/transfer/opportunities")).json()
    # Only one pack touches vault-forge → nothing to transfer to.
    assert all(t["forge_cap"] != "vault-forge" for t in res["transfers"])


async def test_no_transfer_when_recipient_already_covered(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a = _pack(db_session, pack_id="pack.x")
    b = _pack(db_session, pack_id="pack.y")
    for _ in range(4):
        _scn(db_session, pack_dbid=a, cap="voice-forge")
    for _ in range(3):
        _scn(db_session, pack_dbid=b, cap="voice-forge")  # already meets min
    await db_session.commit()
    res = (await client.get("/api/transfer/opportunities")).json()
    assert all(t["forge_cap"] != "voice-forge" for t in res["transfers"])

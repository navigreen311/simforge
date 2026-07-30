"""Golden Benchmark Bank governance (§12.5): nomination → council review → freeze."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pack import Scenario

_COUNTER = [0]


async def _a_scenario_id(session: AsyncSession) -> str:
    """Seed a fresh non-golden scenario and return its scenarioId."""
    _COUNTER[0] += 1
    sid = f"scn.cand.{_COUNTER[0]:03d}"
    session.add(
        Scenario(
            scenarioId=sid,
            packId="pk-x",
            title=f"Candidate {sid}",
            tier="intermediate",
            testedAgentVillageId="taylor_zhang",
            yamlPath=f"{sid}.yml",
            yamlHash="h",
            sloSeconds=60,
            isGolden=False,
        )
    )
    await session.commit()
    return sid


async def test_two_of_three_approval_freezes_scenario(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    sid = await _a_scenario_id(db_session)
    created = (
        await client.post(
            "/api/golden/nominations",
            json={
                "scenario_id": sid,
                "nominated_by": "senior_engineer",
                "rationale": "stable, discriminating, production-representative",
                "inter_rater_reliability": 0.88,
            },
        )
    ).json()
    assert created["status"] == "pending"
    nid = created["id"]

    # First vote: not yet quorum.
    r1 = (
        await client.post(
            f"/api/golden/nominations/{nid}/review",
            json={"approver": "ivan", "decision": "approve"},
        )
    ).json()
    assert r1["status"] == "pending"

    # Second vote reaches two_of_three → frozen.
    r2 = (
        await client.post(
            f"/api/golden/nominations/{nid}/review",
            json={"approver": "administrator", "decision": "approve"},
        )
    ).json()
    assert r2["status"] == "frozen"
    assert r2["frozen_by"] == "administrator"

    # The scenario is now in the gold set.
    scn = (
        await db_session.execute(select(Scenario).where(Scenario.scenarioId == sid))
    ).scalar_one()
    assert scn.isGolden is True


async def test_rejection_leaves_scenario_untouched(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    sid = await _a_scenario_id(db_session)
    nid = (
        await client.post(
            "/api/golden/nominations",
            json={"scenario_id": sid, "nominated_by": "senior_engineer"},
        )
    ).json()["id"]
    (
        await client.post(
            f"/api/golden/nominations/{nid}/review",
            json={"approver": "ivan", "decision": "reject"},
        )
    )
    r2 = (
        await client.post(
            f"/api/golden/nominations/{nid}/review",
            json={"approver": "administrator", "decision": "reject"},
        )
    ).json()
    assert r2["status"] == "rejected"
    scn = (
        await db_session.execute(select(Scenario).where(Scenario.scenarioId == sid))
    ).scalar_one()
    assert scn.isGolden is False


async def test_duplicate_open_nomination_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    sid = await _a_scenario_id(db_session)
    first = await client.post(
        "/api/golden/nominations",
        json={"scenario_id": sid, "nominated_by": "senior_engineer"},
    )
    assert first.status_code == 200
    dup = await client.post(
        "/api/golden/nominations",
        json={"scenario_id": sid, "nominated_by": "administrator"},
    )
    assert dup.status_code == 400
    assert "open nomination" in dup.json()["detail"]


async def test_withdraw_nomination(client: AsyncClient, db_session: AsyncSession) -> None:
    sid = await _a_scenario_id(db_session)
    nid = (
        await client.post(
            "/api/golden/nominations",
            json={"scenario_id": sid, "nominated_by": "senior_engineer"},
        )
    ).json()["id"]
    w = (
        await client.post(
            f"/api/golden/nominations/{nid}/withdraw",
            json={"actor": "senior_engineer"},
        )
    ).json()
    assert w["status"] == "withdrawn"
    listing = (await client.get("/api/golden/nominations?status=pending")).json()
    assert all(n["id"] != nid for n in listing["nominations"])

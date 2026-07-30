"""Production Outcome Correlation (v1.1): cert-vs-production miscalibration detection."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert
from src.utils.time import utcnow


async def _certify(session: AsyncSession, village_id: str, cap: str) -> None:
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == village_id))
    ).scalar_one()
    session.add(
        AgentCert(
            agentId=agent.id,
            forgeCap=cap,
            tier="foundational",
            status="active",
            issuedAt=utcnow(),
            expiresAt=utcnow(),
            certSnapshotId=f"cs-{village_id}-{cap}",
        )
    )
    await session.commit()


async def test_empty_when_no_outcomes(client: AsyncClient) -> None:
    res = (await client.get("/api/production-outcomes/correlation")).json()
    assert res["measured_pairs"] == 0
    assert res["findings"] == []


async def test_certified_underperformer_flagged(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _certify(db_session, "taylor_zhang", "capital-forge")
    await client.post(
        "/api/production-outcomes/",
        json={
            "agent_village_id": "taylor_zhang",
            "forge_cap": "capital-forge",
            "outcome_score": 0.55,
        },
    )
    res = (await client.get("/api/production-outcomes/correlation")).json()
    assert res["summary"]["cert_overstates"] == 1
    f = res["findings"][0]
    assert f["kind"] == "cert_overstates_readiness"
    assert f["agent"] == "taylor_zhang"


async def test_uncertified_overperformer_flagged(client: AsyncClient) -> None:
    # No cert for david_kim; strong production score → under_certified.
    await client.post(
        "/api/production-outcomes/",
        json={
            "agent_village_id": "david_kim",
            "forge_cap": "vault-forge",
            "outcome_score": 0.92,
        },
    )
    res = (await client.get("/api/production-outcomes/correlation")).json()
    assert res["summary"]["under_certified"] == 1
    assert res["findings"][0]["kind"] == "under_certified"


async def test_aligned_not_flagged(client: AsyncClient, db_session: AsyncSession) -> None:
    await _certify(db_session, "taylor_zhang", "capital-forge")
    await client.post(
        "/api/production-outcomes/",
        json={
            "agent_village_id": "taylor_zhang",
            "forge_cap": "capital-forge",
            "outcome_score": 0.88,
        },
    )
    res = (await client.get("/api/production-outcomes/correlation")).json()
    assert res["summary"]["aligned"] == 1
    assert res["summary"]["miscalibrated"] == 0


async def test_latest_outcome_wins(client: AsyncClient) -> None:
    for score in (0.30, 0.95):
        await client.post(
            "/api/production-outcomes/",
            json={
                "agent_village_id": "jennifer_adams",
                "forge_cap": "vault-forge",
                "outcome_score": score,
            },
        )
    res = (await client.get("/api/production-outcomes/correlation")).json()
    assert res["measured_pairs"] == 1  # collapsed to latest per (agent, cap)
    # Latest is 0.95, uncertified → under_certified.
    assert res["summary"]["under_certified"] == 1

"""Autonomy auto-triggers (§11.2): downgrade targets + criteria promotion (L4→L5 via approval)."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert, CertSnapshot
from src.models.pack import Pack, Scenario
from src.models.run import Run
from src.models.scorecard import Scorecard
from src.services.cert.autonomy_triggers import (
    evaluate_promotion,
    on_cognitive_alert,
    on_compliance_violation,
    on_dependency_change,
)
from src.utils.time import utcnow


async def _agent(session: AsyncSession, level: str) -> Agent:
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == "david_kim"))
    ).scalar_one()
    agent.currentAutonomyLevel = level
    await session.commit()
    return agent


async def test_compliance_violation_drops_to_l2(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/api/packs/", json={"pack_dir": _gs()})
    agent = await _agent(db_session, "L5")
    await on_compliance_violation(db_session, agent, reason="test")
    await db_session.commit()
    assert agent.currentAutonomyLevel == "L2"


async def test_cognitive_alert_drops_to_l3(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post("/api/packs/", json={"pack_dir": _gs()})
    agent = await _agent(db_session, "L5")
    await on_cognitive_alert(db_session, agent, reason="arc_fragmentation")
    await db_session.commit()
    assert agent.currentAutonomyLevel == "L3"


async def test_dependency_change_drops_to_l3(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post("/api/packs/", json={"pack_dir": _gs()})
    agent = await _agent(db_session, "L4")
    await on_dependency_change(db_session, agent, reason="forge upgrade")
    await db_session.commit()
    assert agent.currentAutonomyLevel == "L3"


async def test_drop_target_is_a_floor_not_a_move(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # An agent already below the target is unchanged (compliance→L2 from L1 stays L1).
    await client.post("/api/packs/", json={"pack_dir": _gs()})
    agent = await _agent(db_session, "L1")
    await on_compliance_violation(db_session, agent, reason="test")
    await db_session.commit()
    assert agent.currentAutonomyLevel == "L1"


async def test_promotion_blocked_without_streak(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/api/packs/", json={"pack_dir": _gs()})
    agent = await _agent(db_session, "L2")
    await _issue_cert(db_session, agent)
    outcome = await evaluate_promotion(db_session, agent)
    assert outcome.eligible is False and "streak" in outcome.detail


async def test_practice_streak_does_not_open_an_l5_approval(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """ADR-0157 ruling 1: three clean practice runs plus a practice crisis pass used to open an
    L4-to-L5 approval request. Practice runs are not a streak, so nothing opens."""
    from src.models.approval import ApprovalRequest

    await client.post("/api/packs/", json={"pack_dir": _gs()})
    agent = await _agent(db_session, "L4")
    await _issue_cert(db_session, agent)
    await _seed_clean_streak(db_session, agent, advanced_crisis=True)
    outcome = await evaluate_promotion(db_session, agent)
    assert outcome.action == "none" and outcome.eligible is False
    assert outcome.detail == "clean streak 0/3"
    assert agent.currentAutonomyLevel == "L4"
    assert (await db_session.execute(select(ApprovalRequest))).scalars().all() == []


async def test_practice_streak_does_not_promote_l3_to_l4(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """ADR-0157 ruling 1: the same practice streak used to move L3 to L4 directly."""
    from src.models.cert import AutonomyEvent

    await client.post("/api/packs/", json={"pack_dir": _gs()})
    agent = await _agent(db_session, "L3")
    await _issue_cert(db_session, agent)
    await _seed_clean_streak(db_session, agent, advanced_crisis=True)
    outcome = await evaluate_promotion(db_session, agent)
    assert outcome.action == "none" and agent.currentAutonomyLevel == "L3"
    events = (
        (await db_session.execute(select(AutonomyEvent).where(AutonomyEvent.agentId == agent.id)))
        .scalars()
        .all()
    )
    assert events == []


# --- helpers ---


def _gs() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[4] / "packs" / "greenstone" / "v1")


async def _issue_cert(session: AsyncSession, agent: Agent) -> None:
    now = utcnow()
    snap = CertSnapshot(
        snapshotId=f"certsnap:auto-{agent.id[:6]}",
        certType="agent_forge_cap",
        subject=agent.villageAgentId,
        forgeCap="cre-forge.demo.auto",
        tier="foundational",
        issuedAt=now,
        expiresAt=now + timedelta(days=90),
        pinnedVersions={},
        evidenceBundleRef="e",
        signingKeyId="k",
        signature="s",
        contentHash="c",
    )
    session.add(snap)
    await session.flush()
    session.add(
        AgentCert(
            agentId=agent.id,
            forgeCap="cre-forge.demo.auto",
            tier="foundational",
            status="active",
            issuedAt=now,
            expiresAt=now + timedelta(days=90),
            certSnapshotId=snap.id,
        )
    )
    await session.commit()


async def _seed_clean_streak(session: AsyncSession, agent: Agent, *, advanced_crisis: bool) -> None:
    pack = (await session.execute(select(Pack))).scalars().first()
    scenario = Scenario(
        scenarioId="scn.auto.crisis" if advanced_crisis else "scn.auto.found",
        packId=pack.id,
        title="Auto streak",
        tier="advanced_crisis" if advanced_crisis else "foundational",
        testedAgentVillageId=agent.villageAgentId,
        testedForgeCaps=["cre-forge.demo.auto"],
        sloSeconds=120,
        seed=1,
        yamlPath="auto.yml",
        yamlHash="h",
    )
    session.add(scenario)
    await session.flush()
    for i in range(3):
        run = Run(
            runId=f"run-auto-{agent.id[:6]}-{i}",
            scenarioId=scenario.id,
            packId=pack.id,
            agentId=agent.id,
            executionMode="sandbox",
            narrativeMode="protected",
            blindMode=False,
            status="passed",
            startedAt=utcnow() - timedelta(minutes=10 - i),
        )
        session.add(run)
        await session.flush()
        session.add(Scorecard(runId=run.id, readinessGatePassed=True, p2Compliance=True))
    await session.commit()

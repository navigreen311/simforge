"""Regression sweep: a verified prior-pass/now-fail flip auto-suspends the covering cert (§9.2)."""

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
from src.services.evaluation.regression_sweep import find_and_suspend_regressions
from src.utils.time import utcnow

FORGE_CAP = "cre-forge.demo.regression"


async def _seed_scenario(session: AsyncSession) -> tuple[Agent, Scenario]:
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == "david_kim"))
    ).scalar_one()
    pack = (await session.execute(select(Pack))).scalars().first()
    scenario = Scenario(
        scenarioId="scn.reg.001",
        packId=pack.id,
        title="Regression probe",
        tier="foundational",
        testedAgentVillageId="david_kim",
        testedForgeCaps=[FORGE_CAP],
        sloSeconds=120,
        seed=1,
        yamlPath="scn.reg.001.yml",
        yamlHash="hash",
    )
    session.add(scenario)
    await session.flush()
    return agent, scenario


async def _run_with_card(
    session: AsyncSession, agent: Agent, scenario: Scenario, *, passed: bool, minutes_ago: int
) -> Run:
    run = Run(
        runId=f"run-reg-{minutes_ago}",
        scenarioId=scenario.id,
        packId=scenario.packId,
        agentId=agent.id,
        executionMode="sandbox",
        narrativeMode="protected",
        blindMode=False,
        status="passed" if passed else "failed",
        startedAt=utcnow() - timedelta(minutes=minutes_ago),
    )
    session.add(run)
    await session.flush()
    session.add(Scorecard(runId=run.id, readinessGatePassed=passed, p2Compliance=True))
    await session.flush()
    return run


async def _issue_active_cert(session: AsyncSession, agent: Agent) -> AgentCert:
    now = utcnow()
    snap = CertSnapshot(
        snapshotId="certsnap:reg",
        certType="agent_forge_cap",
        subject="david_kim",
        forgeCap=FORGE_CAP,
        tier="foundational",
        issuedAt=now,
        expiresAt=now + timedelta(days=90),
        pinnedVersions={},
        evidenceBundleRef="ev",
        signingKeyId="k",
        signature="s",
        contentHash="c",
    )
    session.add(snap)
    await session.flush()
    cert = AgentCert(
        agentId=agent.id,
        forgeCap=FORGE_CAP,
        tier="foundational",
        status="active",
        issuedAt=now,
        expiresAt=now + timedelta(days=90),
        certSnapshotId=snap.id,
    )
    session.add(cert)
    await session.flush()
    return cert


async def test_flip_suspends_cert(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post("/api/packs/", json={"pack_dir": _greenstone()})
    agent, scenario = await _seed_scenario(db_session)
    await _issue_active_cert(db_session, agent)
    # Prior run passed; the most-recent run failed → a verified flip.
    await _run_with_card(db_session, agent, scenario, passed=True, minutes_ago=60)
    await _run_with_card(db_session, agent, scenario, passed=False, minutes_ago=1)
    await db_session.commit()

    report = await find_and_suspend_regressions(db_session)
    assert report.scanned_certs >= 1
    assert any(f.scenario_id == "scn.reg.001" for f in report.flips)
    cert = (
        await db_session.execute(select(AgentCert).where(AgentCert.forgeCap == FORGE_CAP))
    ).scalar_one()
    assert cert.status == "suspended"


async def test_no_flip_when_still_passing(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post("/api/packs/", json={"pack_dir": _greenstone()})
    agent, scenario = await _seed_scenario(db_session)
    await _issue_active_cert(db_session, agent)
    await _run_with_card(db_session, agent, scenario, passed=True, minutes_ago=60)
    await _run_with_card(db_session, agent, scenario, passed=True, minutes_ago=1)
    await db_session.commit()

    report = await find_and_suspend_regressions(db_session)
    assert report.flips == []
    cert = (
        await db_session.execute(select(AgentCert).where(AgentCert.forgeCap == FORGE_CAP))
    ).scalar_one()
    assert cert.status == "active"


async def test_status_endpoint_is_dry_run(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post("/api/packs/", json={"pack_dir": _greenstone()})
    agent, scenario = await _seed_scenario(db_session)
    await _issue_active_cert(db_session, agent)
    await _run_with_card(db_session, agent, scenario, passed=True, minutes_ago=60)
    await _run_with_card(db_session, agent, scenario, passed=False, minutes_ago=1)
    await db_session.commit()

    status = (await client.get("/api/regression/status")).json()
    assert len(status["flips"]) >= 1 and status["suspended_cert_ids"] == []
    # Dry run did not suspend.
    cert = (
        await db_session.execute(select(AgentCert).where(AgentCert.forgeCap == FORGE_CAP))
    ).scalar_one()
    assert cert.status == "active"


def _greenstone() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[4] / "packs" / "greenstone" / "v1")

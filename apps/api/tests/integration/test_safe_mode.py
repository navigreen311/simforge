"""Persisted scoped safe mode (§11.7): activate/deactivate, scope status, auto-trigger sweep."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.pack import Pack, Scenario
from src.models.run import Run
from src.models.scorecard import Scorecard
from src.services.governance import safe_mode_service
from src.utils.time import utcnow

GREENSTONE = None


def _gs() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[4] / "packs" / "greenstone" / "v1")


async def test_activate_deactivate_scoped_via_api(client: AsyncClient) -> None:
    # Global off initially.
    assert (await client.get("/api/constitution/safe-mode/status")).json()["active"] is False
    # Activate a forge-scoped safe mode.
    body = (
        await client.post(
            "/api/constitution/safe-mode",
            json={
                "active": True,
                "reason": "voice incident",
                "scope_type": "forge",
                "scope_value": "voiceforge",
            },
        )
    ).json()
    assert body["active"] is True
    assert body["states"][0]["scope_type"] == "forge"
    # Deactivate that scope.
    after = (
        await client.post(
            "/api/constitution/safe-mode",
            json={"active": False, "scope_type": "forge", "scope_value": "voiceforge"},
        )
    ).json()
    assert after["active"] is False


async def test_bad_scope_type_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/constitution/safe-mode",
        json={"active": True, "scope_type": "galaxy", "scope_value": "x"},
    )
    assert resp.status_code == 400


async def test_multiple_scopes_active_at_once(client: AsyncClient) -> None:
    await client.post(
        "/api/constitution/safe-mode",
        json={"active": True, "scope_type": "jurisdiction", "scope_value": "US-NV"},
    )
    await client.post(
        "/api/constitution/safe-mode",
        json={"active": True, "scope_type": "forge", "scope_value": "capitalforge"},
    )
    status = (await client.get("/api/constitution/safe-mode/status")).json()
    scopes = {(s["scope_type"], s["scope_value"]) for s in status["states"]}
    assert ("jurisdiction", "US-NV") in scopes and ("forge", "capitalforge") in scopes


async def test_auto_trigger_on_compliance_spike(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/api/packs/", json={"pack_dir": _gs()})
    agent = (
        await db_session.execute(select(Agent).where(Agent.villageAgentId == "david_kim"))
    ).scalar_one()
    pack = (await db_session.execute(select(Pack))).scalars().first()
    scenario = Scenario(
        scenarioId="scn.sm.001",
        packId=pack.id,
        title="sm",
        tier="foundational",
        testedAgentVillageId="david_kim",
        testedForgeCaps=["cre-forge.demo.sm"],
        sloSeconds=60,
        seed=1,
        yamlPath="sm.yml",
        yamlHash="h",
    )
    db_session.add(scenario)
    await db_session.flush()
    # 5 compliance-failing runs within the hour → auto-trigger fires.
    for i in range(5):
        run = Run(
            runId=f"run-sm-{i}",
            scenarioId=scenario.id,
            packId=pack.id,
            agentId=agent.id,
            executionMode="sandbox",
            narrativeMode="protected",
            blindMode=False,
            status="failed",
            startedAt=utcnow() - timedelta(minutes=i),
        )
        db_session.add(run)
        await db_session.flush()
        db_session.add(Scorecard(runId=run.id, readinessGatePassed=False, p2Compliance=False))
    await db_session.commit()

    row = await safe_mode_service.maybe_auto_activate(db_session)
    assert row is not None and row.autoTriggered is True
    status = await safe_mode_service.status(db_session)
    assert status["global_active"] is True


async def test_auto_trigger_no_op_below_threshold(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/api/packs/", json={"pack_dir": _gs()})
    row = await safe_mode_service.maybe_auto_activate(db_session)
    assert row is None

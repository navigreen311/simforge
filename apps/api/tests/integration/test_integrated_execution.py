"""Integration: PDP-gated integrated execution + audit ledger + revert (ADR-0025)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.agent import Agent
from src.models.pack import Pack

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
# scn.gs.buy.002 (david_kim) exercises these two caps:
CERTED_CAP = "capitalforge.emd.release"
UNCERTED_CAP = "cre-forge.deals.assignment"


async def test_flag_off_stays_sandbox(client: AsyncClient) -> None:
    # Default deployment: integrated execution is off, so an integrated request still runs sandbox.
    assert (await client.get("/api/execution/status")).json()[
        "integrated_execution_enabled"
    ] is False
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = (
        await client.post("/api/scenarios/scn.gs.buy.002/run", params={"integrated": True})
    ).json()
    detail = (await client.get(f"/api/runs/{run['run_id']}")).json()
    assert detail["execution_mode"] == "sandbox"
    ledger = (await client.get(f"/api/execution/run/{run['run_id']}/actions")).json()
    assert ledger["actions"] == []


async def _issue_cert_and_elevate(client: AsyncClient, db_session: AsyncSession) -> None:
    """Certify david_kim for CERTED_CAP and elevate autonomy to L5 (so the PDP allows it)."""
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    issue = await client.post(
        "/api/certs/agent/issue",
        json={
            "agent_village_id": "david_kim",
            "forge_cap": CERTED_CAP,
            "tier": "foundational",
            "battery_run_ids": [run["run_id"]],
            "approver_id": "ivan",
            "pack_id": "pack.greenstone.v1",
        },
    )
    assert issue.status_code == 200, issue.text
    agent = (
        await db_session.execute(select(Agent).where(Agent.villageAgentId == "david_kim"))
    ).scalar_one()
    agent.currentAutonomyLevel = "L5"
    pack = (
        await db_session.execute(select(Pack).where(Pack.packId == "pack.greenstone.v1"))
    ).scalar_one()
    pack.integratedRunsAllowed = True
    await db_session.commit()


async def test_integrated_applies_certified_blocks_uncertified(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "integrated_execution_enabled", True)
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    await _issue_cert_and_elevate(client, db_session)

    run = (
        await client.post("/api/scenarios/scn.gs.buy.002/run", params={"integrated": True})
    ).json()
    detail = (await client.get(f"/api/runs/{run['run_id']}")).json()
    assert detail["execution_mode"] == "integrated"

    ledger = (await client.get(f"/api/execution/run/{run['run_id']}/actions")).json()["actions"]
    by_cap = {a["action"]: a for a in ledger}
    # Certified cap at L5 → allowed → applied; uncertified cap → denied → blocked.
    assert by_cap[CERTED_CAP]["applied"] is True and by_cap[CERTED_CAP]["decision"] == "allow"
    assert by_cap[UNCERTED_CAP]["applied"] is False
    assert by_cap[UNCERTED_CAP]["reason_code"] == "no_certification"

    # Revert the applied action → compensating ledger entry.
    action_id = by_cap[CERTED_CAP]["action_id"]
    rv = await client.post(
        f"/api/execution/run/{run['run_id']}/actions/{action_id}/revert", json={"actor": "ivan"}
    )
    assert rv.status_code == 200 and rv.json()["status"] == "reverted"
    after = (await client.get(f"/api/execution/run/{run['run_id']}/actions")).json()["actions"]
    reverted = next(a for a in after if a["action_id"] == action_id)
    assert reverted["reverted"] is True and reverted["status"] == "reverted"


async def test_cannot_revert_blocked_action(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "integrated_execution_enabled", True)
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    await _issue_cert_and_elevate(client, db_session)
    run = (
        await client.post("/api/scenarios/scn.gs.buy.002/run", params={"integrated": True})
    ).json()
    ledger = (await client.get(f"/api/execution/run/{run['run_id']}/actions")).json()["actions"]
    blocked = next(a for a in ledger if a["applied"] is False)
    rv = await client.post(
        f"/api/execution/run/{run['run_id']}/actions/{blocked['action_id']}/revert",
        json={"actor": "ivan"},
    )
    assert rv.status_code == 400 and "not applied" in rv.json()["detail"].lower()

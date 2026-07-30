"""Blind-mode: real behavioural redaction + cert-time ≥pct floor (§15.3, B4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.run import Run

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
FORGE_CAP = "cre-forge.call_center.outbound_seller_outreach"


async def test_blind_run_redacts_scenario_title_from_transcript(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    # A normal run: the complication text carries the scenario title into the transcript.
    normal = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()
    normal_run = (
        await db_session.execute(select(Run).where(Run.runId == normal["run_id"]))
    ).scalar_one()
    title = "Cold outreach to a motivated seller"
    normal_blob = " ".join(t.get("content", "") for t in (normal_run.transcript or []))

    # A blind run: the title must not appear anywhere the agent can see, and the run is flagged.
    blind = (await client.post("/api/scenarios/scn.gs.src.001/run", params={"blind": True})).json()
    assert blind["blind_mode"] is True
    blind_run = (
        await db_session.execute(select(Run).where(Run.runId == blind["run_id"]))
    ).scalar_one()
    blind_blob = " ".join(t.get("content", "") for t in (blind_run.transcript or []))
    assert title not in blind_blob
    # The normal run either shows the title (complication) or at least is not redacted the same way.
    assert normal_blob != blind_blob or title in normal_blob


async def test_cert_blind_floor_enforced_only_when_flag_on(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = (await client.post("/api/scenarios/scn.gs.src.001/run")).json()  # non-blind
    payload = {
        "agent_village_id": "david_kim",
        "forge_cap": FORGE_CAP,
        "tier": "foundational",
        "battery_run_ids": [run["run_id"]],
        "approver_id": "ivan",
        "pack_id": "pack.greenstone.v1",
    }
    # Flag on → a 0%-blind battery is rejected by the blind floor.
    monkeypatch.setattr(settings, "cert_enforce_blind_mode", True)
    blocked = await client.post("/api/certs/agent/issue", json=payload)
    assert blocked.status_code == 400 and "blind" in blocked.json()["detail"].lower()

    # A blind run in the battery satisfies the floor.
    blind = (await client.post("/api/scenarios/scn.gs.src.001/run", params={"blind": True})).json()
    payload["battery_run_ids"] = [blind["run_id"]]
    ok = await client.post("/api/certs/agent/issue", json=payload)
    assert ok.status_code == 200, ok.text

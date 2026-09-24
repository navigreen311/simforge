"""Scenario Truth Review Gate (v1.1): checklist attestation + optional run gate."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.pack import Pack, Scenario

_N = [0]

FULL = {
    "realistic": True,
    "outcome_correct": True,
    "no_fabrication": True,
    "compliance_accurate": True,
}


async def _pack(session: AsyncSession) -> str:
    """The Pack a Scenario references. Postgres refuses a dangling packId."""
    pack = Pack(
        packId=f"pk.tr.{_N[0]:03d}",
        name="truth review",
        version="1.0.0",
        ownerVenture="greenstone",
        ownerHuman="ivan",
        rubricProfile="default",
        yamlPath="p.yml",
        yamlHash="h",
    )
    session.add(pack)
    await session.flush()
    return pack.id


async def _seed(session: AsyncSession) -> str:
    _N[0] += 1
    sid = f"scn.tr.{_N[0]:03d}"
    session.add(
        Scenario(
            scenarioId=sid,
            packId=await _pack(session),
            title="t",
            tier="foundational",
            testedAgentVillageId="taylor_zhang",
            yamlPath="p.yml",
            yamlHash="h",
            sloSeconds=60,
            isGolden=False,
        )
    )
    return sid


async def test_full_checklist_approves(client: AsyncClient, db_session: AsyncSession) -> None:
    sid = await _seed(db_session)
    await db_session.commit()
    res = (
        await client.post(f"/api/truth-review/{sid}", json={"reviewer": "ivan", "checklist": FULL})
    ).json()
    assert res["status"] == "approved"
    assert res["checklist"]["no_fabrication"] is True


async def test_incomplete_checklist_rejects(client: AsyncClient, db_session: AsyncSession) -> None:
    sid = await _seed(db_session)
    await db_session.commit()
    partial = {**FULL, "no_fabrication": False}
    res = (
        await client.post(
            f"/api/truth-review/{sid}", json={"reviewer": "ivan", "checklist": partial}
        )
    ).json()
    assert res["status"] == "rejected"


async def test_unreviewed_worklist(client: AsyncClient, db_session: AsyncSession) -> None:
    sid_a = await _seed(db_session)
    sid_b = await _seed(db_session)
    await db_session.commit()
    await client.post(f"/api/truth-review/{sid_a}", json={"reviewer": "ivan", "checklist": FULL})
    work = (await client.get("/api/truth-review/unreviewed")).json()
    assert sid_b in work["scenario_ids"]
    assert sid_a not in work["scenario_ids"]


async def test_gate_blocks_run_when_enforced(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "truth_gate_enforce", True)
    # scn.gs.src.001 exists in greenstone but is unreviewed.
    await client.post("/api/packs/", json={"pack_dir": _greenstone()})
    blocked = await client.post("/api/scenarios/scn.gs.src.001/run")
    assert blocked.status_code == 403
    assert "truth review" in blocked.json()["detail"].lower()

    # Approve it, then the run is no longer gated by truth review.
    await client.post(
        "/api/truth-review/scn.gs.src.001", json={"reviewer": "ivan", "checklist": FULL}
    )
    allowed = await client.post("/api/scenarios/scn.gs.src.001/run")
    assert allowed.status_code == 200


def _greenstone() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[4] / "packs" / "greenstone" / "v1")

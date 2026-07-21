"""Integration tests for Pack ingestion + packs/scenarios endpoints."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

# apps/api/tests/integration/test_packs.py → repo root is parents[4]
REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
MEDLINK = str(REPO_ROOT / "packs" / "medlink-pro" / "v1")


async def test_ingest_and_list_pack(client: AsyncClient) -> None:
    # Ingest via absolute path
    resp = await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["pack_id"] == "pack.greenstone.v1"
    assert body["scenarios"] == 3

    # List
    lst = await client.get("/api/packs/")
    assert lst.status_code == 200
    assert lst.json()["total"] == 1

    # Detail
    detail = await client.get("/api/packs/pack.greenstone.v1")
    assert detail.status_code == 200
    d = detail.json()
    assert d["ownerVenture"] == "greenstone"
    assert len(d["scenarios"]) == 3
    assert "tcpa" in d["complianceFlags"]


async def test_ingest_is_idempotent(client: AsyncClient) -> None:
    for _ in range(2):
        resp = await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
        assert resp.status_code == 200
    lst = await client.get("/api/packs/")
    assert lst.json()["total"] == 1  # no duplicate pack


async def test_scenarios_endpoints(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": MEDLINK})

    all_scen = await client.get("/api/scenarios/", params={"pack_id": "pack.medlink-pro.v1"})
    assert all_scen.status_code == 200
    assert all_scen.json()["total"] == 3

    crisis = await client.get("/api/scenarios/", params={"tier": "advanced_crisis"})
    assert crisis.status_code == 200
    assert crisis.json()["total"] >= 1

    detail = await client.get("/api/scenarios/scn.ml.cred.001")
    assert detail.status_code == 200
    assert detail.json()["testedAgentVillageId"] == "nina_okafor"


async def test_sign_pack(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    resp = await client.post("/api/packs/pack.greenstone.v1/sign", json={"signed_by": "ivan"})
    assert resp.status_code == 200
    assert resp.json()["signedBy"] == "ivan"

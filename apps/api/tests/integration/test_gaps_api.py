"""Integration tests for gap emission + gap endpoints."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")
MEDLINK = str(REPO_ROOT / "packs" / "medlink-pro" / "v1")


async def test_crisis_run_emits_software_gaps(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    # scn.gs.crisis.003 is advanced_crisis and tests david_kim (seeded)
    run = await client.post("/api/scenarios/scn.gs.crisis.003/run")
    assert run.status_code == 200, run.text

    gaps = await client.get("/api/gaps/software")
    assert gaps.status_code == 200
    body = gaps.json()
    assert body["total"] >= 1
    forges = {g["forge"] for g in body["items"]}
    assert "cre-forge" in forges or "voiceforge" in forges


async def test_gap_dedup_increments_occurrence(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    await client.post("/api/scenarios/scn.gs.crisis.003/run")
    first = (await client.get("/api/gaps/software")).json()["total"]
    await client.post("/api/scenarios/scn.gs.crisis.003/run")
    second = (await client.get("/api/gaps/software")).json()
    # Same gaps → no new tickets, occurrence bumped
    assert second["total"] == first
    assert any(g["occurrenceCount"] >= 2 for g in second["items"])


async def test_healthy_run_has_no_village_os_gaps(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": MEDLINK})
    await client.post("/api/scenarios/scn.ml.place.002/run")  # jennifer_adams, healthy
    vos = await client.get("/api/gaps/village-os")
    assert vos.status_code == 200
    assert vos.json()["total"] == 0


async def test_update_gap_status(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    await client.post("/api/scenarios/scn.gs.crisis.003/run")
    ticket = (await client.get("/api/gaps/software")).json()["items"][0]["ticketId"]
    resp = await client.post(
        f"/api/gaps/software/{ticket}/update-status", json={"status": "triaged"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "triaged"


async def test_top_10_endpoints(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    await client.post("/api/scenarios/scn.gs.crisis.003/run")
    forge_top = await client.get("/api/gaps/top-10/forge/cre-forge")
    assert forge_top.status_code == 200
    vos_top = await client.get("/api/gaps/top-10/village-os")
    assert vos_top.status_code == 200

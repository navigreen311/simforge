"""Venture Registry API tests."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")


async def test_registry_is_seeded(client: AsyncClient) -> None:
    body = (await client.get("/api/ventures/")).json()
    by_slug = {v["slug"]: v for v in body["items"]}
    # the three with packs are active with real flags; the new ones are empty + in_development
    assert by_slug["medlink-pro"]["status"] == "active"
    assert "hipaa" in by_slug["medlink-pro"]["defaultComplianceFlags"]
    assert by_slug["argus"]["status"] == "in_development"
    assert by_slug["argus"]["defaultComplianceFlags"] == []
    assert by_slug["argus"]["capabilityCount"] == 0
    expected = {"greenstone", "medlink-pro", "caregrid", "argus", "collingswood"}
    assert expected <= set(by_slug)
    assert "burkham-wickmont" in by_slug


async def test_venture_detail_counts_packs(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    d = (await client.get("/api/ventures/greenstone")).json()
    assert d["packCount"] == 1
    assert d["packs"][0]["packId"] == "pack.greenstone.v1"
    assert d["packs"][0]["scenarioCount"] == 3
    assert (await client.get("/api/ventures/nope")).status_code == 404


async def test_create_venture(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/ventures/",
        json={"name": "Wexford Labs", "slug": "wexford", "status": "in_development"},
    )
    assert resp.status_code == 201, resp.text
    v = resp.json()
    assert v["slug"] == "wexford"
    assert v["scenarioCode"] == "we"  # auto-derived from slug
    # now visible in the registry (so vocabulary/pack-create can use it)
    vocab = (await client.get("/api/scenario-bank/vocabulary")).json()
    assert "wexford" in vocab["packs"]


async def test_create_duplicate_rejected(client: AsyncClient) -> None:
    assert (
        await client.post("/api/ventures/", json={"name": "Argus", "slug": "argus"})
    ).status_code == 409


async def test_update_venture_status(client: AsyncClient) -> None:
    r = await client.patch(
        "/api/ventures/argus", json={"status": "active", "description": "Now live."}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    assert r.json()["description"] == "Now live."

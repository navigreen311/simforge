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


async def test_list_is_enriched_with_scenario_summary(client: AsyncClient) -> None:
    # Part A: the list row carries scenario count, tier spread, golden count, and flags.
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    item = (await client.get("/api/packs/")).json()["items"][0]
    assert item["scenarioCount"] == 3
    assert sum(item["tierCounts"].values()) == 3
    assert set(item["tierCounts"]) == {"foundational", "intermediate", "advanced_crisis"}
    assert item["goldenCount"] >= 0
    assert "tcpa" in item["complianceFlags"]


async def test_flag_catalog_labels_every_used_flag(client: AsyncClient) -> None:
    # Every flag actually used by a pack must be labeled (no unexplained chip).
    await client.post("/api/packs/", json={"pack_dir": MEDLINK})
    cat = (await client.get("/api/packs/flag-catalog")).json()
    for flag in ["hipaa", "hcqc_nv", "oig_sam", "i9"]:
        assert flag in cat["flags"], flag
        assert cat["flags"][flag]["label"]
        assert cat["flags"][flag]["tooltip"]
    # HIPAA is a PHI flag and maps to the federal jurisdiction.
    assert cat["flags"]["hipaa"]["phi"] is True
    assert cat["flags"]["hipaa"]["jurisdiction"] == "US-FED"
    # Legend copy is present for the non-flag chips.
    assert "venture" in cat["legend"] and "phi" in cat["legend"] and "sandbox" in cat["legend"]


async def test_unknown_flag_gets_readable_fallback() -> None:
    # A flag with no catalog entry still gets a humanized label, never blank.
    from src.services.packs.flag_catalog import describe_flag

    d = describe_flag("some_new_flag")
    assert d["label"] == "Some New Flag"
    assert d["tooltip"]
    assert d["phi"] is False

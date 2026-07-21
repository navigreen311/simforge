"""Integration test: the CareGrid venture pack — multi-forge crisis + CA jurisdiction coverage.

Demonstrates the platform generalizing to a new venture (California home-health staffing): one
crisis run exercises three real Forges, and the pack satisfies US-CA + federal compliance coverage.
"""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
CAREGRID = str(REPO_ROOT / "packs" / "caregrid" / "v1")


async def test_caregrid_crisis_run_emits_three_forge_gaps(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": CAREGRID})
    # scn.cg.audit.003 (advanced_crisis, jennifer_adams) exercises medlink-pro + vaf + voiceforge.
    run = await client.post("/api/scenarios/scn.cg.audit.003/run")
    assert run.status_code == 200, run.text

    trace = (await client.get(f"/api/runs/{run.json()['run_id']}/trace")).json()
    forges_faulted = {
        e["payload"]["forge"] for e in trace["events"] if e["event_type"] == "forge_fault"
    }
    assert {"medlink-pro", "vaf", "voiceforge"} <= forges_faulted

    for forge in ("medlink-pro", "vaf", "voiceforge"):
        gaps = (await client.get("/api/gaps/software", params={"forge": forge})).json()
        assert gaps["total"] >= 1, forge


async def test_caregrid_placement_run_passes_and_scores(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": CAREGRID})
    run = (await client.post("/api/scenarios/scn.cg.place.002/run")).json()
    assert run["status"] == "passed"
    card = (await client.get(f"/api/runs/{run['run_id']}/scorecard")).json()
    assert "readiness_gate_passed" in card


async def test_caregrid_pack_satisfies_california_jurisdiction(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": CAREGRID})
    report = (await client.get("/api/jurisdictions/coverage/pack/pack.caregrid.v1")).json()
    assert report["satisfied"] is True
    assert "US-CA" in report["jurisdictions"] and "US-FED" in report["jurisdictions"]
    # California privacy (ccpa) + health regulator (cdph_ca) are among the required flags.
    assert {"cdph_ca", "ccpa", "hipaa", "oig_sam", "i9"} <= set(report["required_flags"])

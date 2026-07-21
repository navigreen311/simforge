"""Integration: the adversarial suite against a scenario's agent (ADR-0028)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")


async def test_tactics_catalog(client: AsyncClient) -> None:
    tactics = (await client.get("/api/adversarial/tactics")).json()["tactics"]
    assert len(tactics) >= 5
    assert {t["id"] for t in tactics} >= {"authority_pressure", "falsification_bait"}


async def test_agent_resists_the_suite(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    report = (await client.post("/api/adversarial/probe/scenario/scn.gs.src.001")).json()
    assert report["agent"] == "david_kim"
    assert report["probes_run"] == 5
    # The compliant stub agent resists every tactic (no violation markers in its responses).
    assert report["capitulated"] == 0 and report["resistance_rate"] == 1.0
    assert report["failures"] == []
    for r in report["results"]:
        assert r["resisted"] is True


async def test_unknown_scenario_404(client: AsyncClient) -> None:
    resp = await client.post("/api/adversarial/probe/scenario/scn.nope")
    assert resp.status_code == 404

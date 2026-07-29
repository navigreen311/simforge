"""Integration: the adversarial suite against a scenario's agent (ADR-0028)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")


async def test_tactics_catalog(client: AsyncClient) -> None:
    body = (await client.get("/api/adversarial/tactics")).json()
    tactics = body["tactics"]
    # Data-driven catalog expanded to the vertical-relevant classes.
    assert len(tactics) >= 15
    ids = {t["id"] for t in tactics}
    assert {
        "authority_pressure",
        "prompt_injection",
        "phi_disclosure_bait",
        "hipaa_workaround",
        "credential_bypass",
        "title_fraud_bait",
    } <= ids
    # Every tactic carries a plain name + description; detection method is reported.
    assert all(t["name"] and t["description"] for t in tactics)
    assert body["detection"] == "substring"


async def test_agent_resists_the_suite(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    report = (await client.post("/api/adversarial/probe/scenario/scn.gs.src.001")).json()
    assert report["agent"] == "david_kim"
    assert report["probes_run"] >= 15
    assert report["provider"] == "stub" and report["verdict"] == "resisted"
    # The compliant stub agent resists every tactic (no violation markers in its responses).
    assert report["capitulated"] == 0 and report["resistance_rate"] == 1.0
    assert report["failures"] == []
    for r in report["results"]:
        assert r["resisted"] is True
        assert r["name"] and r["injection"]  # each result carries the plain name + what was asked


async def test_probe_persisted_and_arbitrary_agent(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    assert (await client.get("/api/adversarial/history")).json()["probes"] == []
    # Probe an explicit agent via the agent_id override (arbitrary-agent probing).
    report = (
        await client.post(
            "/api/adversarial/probe/scenario/scn.gs.src.001", params={"agent_id": "david_kim"}
        )
    ).json()
    assert report["agent"] == "david_kim"

    hist = (await client.get("/api/adversarial/history")).json()["probes"]
    assert len(hist) == 1
    assert hist[0]["verdict"] == report["verdict"]
    assert hist[0]["ran_at"] and len(hist[0]["results"]) >= 15


async def test_unknown_scenario_404(client: AsyncClient) -> None:
    resp = await client.post("/api/adversarial/probe/scenario/scn.nope")
    assert resp.status_code == 404


async def test_unknown_agent_404(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    resp = await client.post(
        "/api/adversarial/probe/scenario/scn.gs.src.001", params={"agent_id": "nobody"}
    )
    assert resp.status_code == 404

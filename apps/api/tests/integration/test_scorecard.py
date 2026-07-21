"""Integration test: run a scenario and fetch its auto-generated scorecard."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
MEDLINK = str(REPO_ROOT / "packs" / "medlink-pro" / "v1")


async def test_run_produces_scorecard_with_gate(client: AsyncClient) -> None:
    await client.post("/api/packs/", json={"pack_dir": MEDLINK})
    run = (await client.post("/api/scenarios/scn.ml.place.002/run")).json()
    run_id = run["run_id"]

    resp = await client.get(f"/api/runs/{run_id}/scorecard")
    assert resp.status_code == 200, resp.text
    card = resp.json()

    # All 15 dims populated (agent is in the Village fixture → cognitive dims present)
    assert card["p1_correctness"] is not None
    assert card["p2_compliance"] is True
    assert card["c4_arc_narrative_coherence"] == "stable"
    assert card["cognitive_aggregate"] is not None
    assert isinstance(card["readiness_gate_passed"], bool)
    # C5 derives from echo.regret_load=0.12 → 0.88
    assert abs(card["c5_echo_regret_load"] - 0.88) < 1e-6


async def test_scorecard_404_before_eval(client: AsyncClient) -> None:
    resp = await client.get("/api/runs/nonexistent-run/scorecard")
    assert resp.status_code == 404

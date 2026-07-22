"""Village narrative mode (ADR-0035)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
MEDLINK = str(REPO_ROOT / "packs" / "medlink-pro" / "v1")


async def _ingest(client: AsyncClient) -> None:
    resp = await client.post("/api/packs/", json={"pack_dir": MEDLINK})
    assert resp.status_code == 200, resp.text


async def test_protected_run_produces_no_narrative_effect(client: AsyncClient) -> None:
    await _ingest(client)
    # Default narrative mode is "protected" (pack default) → no beat.
    run = (await client.post("/api/scenarios/scn.ml.place.002/run")).json()
    trace = await client.get(f"/api/runs/{run['run_id']}/trace")
    types = {e["event_type"] for e in trace.json()["events"]}
    assert "narrative_effect" not in types

    arc = await client.get("/api/narrative/agent/jennifer_adams/arc")
    assert arc.status_code == 200
    assert arc.json()["arc_length"] == 0


async def test_integrated_narrative_run_accretes_a_beat(client: AsyncClient) -> None:
    await _ingest(client)
    run = (
        await client.post("/api/scenarios/scn.ml.place.002/run?narrative_mode=integrated")
    ).json()

    # The run recorded a narrative_effect trace event.
    trace = await client.get(f"/api/runs/{run['run_id']}/trace")
    effects = [e for e in trace.json()["events"] if e["event_type"] == "narrative_effect"]
    assert len(effects) == 1
    payload = effects[0]["payload"]
    assert payload["agent"] == "jennifer_adams"
    assert "arc_state" in payload and "reputation_delta" in payload and payload["beat"]

    # The agent's arc now has one beat.
    arc = (await client.get("/api/narrative/agent/jennifer_adams/arc")).json()
    assert arc["arc_length"] == 1
    assert arc["beats"][0]["scenario_id"] == "scn.ml.place.002"

    # A second integrated-narrative run extends the arc.
    await client.post("/api/scenarios/scn.ml.place.002/run?narrative_mode=integrated")
    arc2 = (await client.get("/api/narrative/agent/jennifer_adams/arc")).json()
    assert arc2["arc_length"] == 2


async def test_narrative_arc_unknown_agent_404(client: AsyncClient) -> None:
    resp = await client.get("/api/narrative/agent/nobody/arc")
    assert resp.status_code == 404

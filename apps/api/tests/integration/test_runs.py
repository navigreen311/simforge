"""Integration tests for scenario execution + run endpoints."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
MEDLINK = str(REPO_ROOT / "packs" / "medlink-pro" / "v1")


async def _ingest_medlink(client: AsyncClient) -> None:
    resp = await client.post("/api/packs/", json={"pack_dir": MEDLINK})
    assert resp.status_code == 200, resp.text


async def test_run_scenario_end_to_end(client: AsyncClient) -> None:
    await _ingest_medlink(client)

    # scn.ml.place.002 tests jennifer_adams (seeded in conftest + present in Village fixture)
    run_resp = await client.post("/api/scenarios/scn.ml.place.002/run")
    assert run_resp.status_code == 200, run_resp.text
    run = run_resp.json()
    assert run["status"] in {"passed", "failed"}
    assert run["agent_village_id"] == "jennifer_adams"
    assert run["scenario_id"] == "scn.ml.place.002"
    assert run["tokens_used"] > 0
    run_id = run["run_id"]

    # Appears in the run list
    lst = await client.get("/api/runs/")
    assert lst.status_code == 200
    assert lst.json()["total"] == 1

    # Transcript persisted
    tr = await client.get(f"/api/runs/{run_id}/transcript")
    assert tr.status_code == 200
    turns = tr.json()["turns"]
    assert turns[0]["role"] == "scenario"
    assert any(t["role"] == "agent" for t in turns)

    # Trace persisted with lifecycle events
    trace = await client.get(f"/api/runs/{run_id}/trace")
    assert trace.status_code == 200
    types = {e["event_type"] for e in trace.json()["events"]}
    assert {"cold_open", "agent_response", "wrap"} <= types


async def test_run_unregistered_agent_404(client: AsyncClient) -> None:
    await _ingest_medlink(client)
    # scn.ml.cred.001 tests nina_okafor, who is NOT seeded in the test DB
    resp = await client.post("/api/scenarios/scn.ml.cred.001/run")
    assert resp.status_code == 404


async def test_run_missing_scenario_404(client: AsyncClient) -> None:
    resp = await client.post("/api/scenarios/scn.nope.999/run")
    assert resp.status_code == 404

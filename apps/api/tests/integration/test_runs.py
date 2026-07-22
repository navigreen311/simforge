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


async def test_replay_is_deterministic(client: AsyncClient) -> None:
    """A stub replay reproduces the run: deterministic, identical transcript, no scorecard diff."""
    await _ingest_medlink(client)
    run = (await client.post("/api/scenarios/scn.ml.place.002/run")).json()
    original_id = run["run_id"]

    resp = await client.post(f"/api/runs/{original_id}/replay")
    assert resp.status_code == 200, resp.text
    cmp = resp.json()

    assert cmp["original_run_id"] == original_id
    assert cmp["replay_run_id"] != original_id  # replay is a fresh run
    assert cmp["scenario_id"] == "scn.ml.place.002"
    assert cmp["deterministic"] is True
    assert cmp["transcript_identical"] is True
    assert cmp["scorecard_diffs"] == []
    assert cmp["original_gate_passed"] == cmp["replay_gate_passed"]

    # The replay run exists and is tagged with a provenance trace event pointing at the original.
    trace = await client.get(f"/api/runs/{cmp['replay_run_id']}/trace")
    assert trace.status_code == 200
    replay_events = [e for e in trace.json()["events"] if e["event_type"] == "replay"]
    assert replay_events and replay_events[0]["payload"]["original_run_id"] == original_id


async def test_replay_missing_run_404(client: AsyncClient) -> None:
    resp = await client.post("/api/runs/does-not-exist/replay")
    assert resp.status_code == 404


async def test_run_unregistered_agent_404(client: AsyncClient) -> None:
    await _ingest_medlink(client)
    # scn.ml.cred.001 tests nina_okafor, who is NOT seeded in the test DB
    resp = await client.post("/api/scenarios/scn.ml.cred.001/run")
    assert resp.status_code == 404


async def test_run_missing_scenario_404(client: AsyncClient) -> None:
    resp = await client.post("/api/scenarios/scn.nope.999/run")
    assert resp.status_code == 404

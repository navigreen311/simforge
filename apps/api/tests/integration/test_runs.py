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


# ── Live run monitor (Part E) ───────────────────────────────────────────────


async def test_live_executor_persists_incrementally(client, db_session, village_reader) -> None:
    # The live path persists transcript + trace as it goes; the shared cursor prevents any
    # trace event being written twice (incremental + final).
    from datetime import UTC, datetime

    from sqlalchemy import select
    from ulid import ULID

    from src.models.agent import Agent
    from src.models.pack import Pack, Scenario
    from src.models.run import Run, TraceEvent
    from src.services.runner.execute import _execute_into_run

    await _ingest_medlink(client)
    scenario = (
        await db_session.execute(select(Scenario).where(Scenario.scenarioId == "scn.ml.place.002"))
    ).scalar_one()
    pack = (await db_session.execute(select(Pack).where(Pack.id == scenario.packId))).scalar_one()
    agent = (
        await db_session.execute(
            select(Agent).where(Agent.villageAgentId == scenario.testedAgentVillageId)
        )
    ).scalar_one()
    run = Run(
        runId=str(ULID()),
        scenarioId=scenario.id,
        packId=pack.id,
        agentId=agent.id,
        executionMode="sandbox",
        narrativeMode="protected",
        blindMode=False,
        status="running",
        startedAt=datetime.now(UTC),
    )
    db_session.add(run)
    await db_session.flush()

    await _execute_into_run(
        db_session, run, scenario, pack, agent, village_reader, None, False, live=True
    )
    assert run.transcript  # transcript persisted
    assert run.status in {"passed", "failed"}
    events = (
        (await db_session.execute(select(TraceEvent).where(TraceEvent.runId == run.id)))
        .scalars()
        .all()
    )
    types = {e.eventType for e in events}
    assert {"cold_open", "agent_response", "wrap"} <= types
    assert len([e for e in events if e.eventType == "wrap"]) == 1  # no double-write


async def test_live_view_of_completed_run(client: AsyncClient) -> None:
    await _ingest_medlink(client)
    run = (await client.post("/api/scenarios/scn.ml.place.002/run")).json()
    live = (await client.get(f"/api/runs/{run['run_id']}/live")).json()
    assert live["done"] is True
    assert live["status"] in {"passed", "failed"}
    assert live["agent_village_id"] == "jennifer_adams"
    assert live["scenario_id"] == "scn.ml.place.002"
    assert any(t["role"] == "agent" for t in live["transcript"])
    assert {"cold_open", "agent_response", "wrap"} <= {e["event_type"] for e in live["trace"]}
    assert live["scorecard"] is not None  # scorecard fills in once scoring completes
    assert live["elapsed_ms"] >= 0


async def test_launch_live_returns_queued_run(client: AsyncClient) -> None:
    await _ingest_medlink(client)
    r = await client.post("/api/scenarios/scn.ml.place.002/run-live")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run_id"]
    assert body["agent_village_id"] == "jennifer_adams"
    # the run row is created (and thus watchable) before the background task starts
    got = await client.get(f"/api/runs/{body['run_id']}")
    assert got.status_code == 200
    assert got.json()["status"] in {"queued", "running", "scoring", "passed", "failed"}

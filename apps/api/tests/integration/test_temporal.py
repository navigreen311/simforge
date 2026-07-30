"""Temporal Realism Engine (v1.1): virtual-turn simulation of delayed events + time-bombs."""

from __future__ import annotations

from httpx import AsyncClient

from src.services.temporal.engine import simulate


def test_time_bomb_defused_before_deadline() -> None:
    res = simulate(
        events=[{"at_turn": 1, "kind": "delayed", "description": "regulator calls back"}],
        time_bombs=[
            {"deadline_turn": 3, "defuse": "escalate", "consequence": "breach"},
        ],
        agent_turns=["ack", "investigate", "escalate to compliance", "close"],
    )
    assert res["passed"] is True
    assert res["detonations"] == 0
    assert res["time_bombs"][0]["status"] == "defused"
    assert res["time_bombs"][0]["defused_turn"] == 2


def test_time_bomb_detonates_when_missed() -> None:
    res = simulate(
        events=[],
        time_bombs=[{"deadline_turn": 1, "defuse": "escalate", "consequence": "data breach"}],
        agent_turns=["stall", "stall", "escalate too late"],
    )
    assert res["passed"] is False
    assert res["detonations"] == 1
    assert res["time_bombs"][0]["status"] == "detonated"
    assert res["realism_score"] == 0.0


def test_realism_score_partial() -> None:
    res = simulate(
        events=[],
        time_bombs=[
            {"deadline_turn": 5, "defuse": "notify", "consequence": "x"},
            {"deadline_turn": 0, "defuse": "freeze", "consequence": "y"},
        ],
        agent_turns=["notify the client", "continue"],  # notify defuses bomb 1; bomb 2 missed
    )
    assert res["detonations"] == 1
    assert res["realism_score"] == 0.5


async def test_simulate_endpoint(client: AsyncClient) -> None:
    body = {
        "events": [{"at_turn": 2, "kind": "async", "description": "late signal"}],
        "time_bombs": [{"deadline_turn": 2, "defuse": "halt", "consequence": "loss"}],
        "agent_turns": ["look", "halt trading", "done"],
    }
    res = (await client.post("/api/temporal/simulate", json=body)).json()
    assert res["passed"] is True
    # The async event at turn 2 shows on the timeline.
    turn2 = next(t for t in res["timeline"] if t["turn"] == 2)
    assert turn2["events"][0]["kind"] == "async"


async def test_store_and_simulate_stored(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/api/temporal/",
            json={
                "name": "trading halt drill",
                "time_bombs": [{"deadline_turn": 1, "defuse": "halt", "consequence": "loss"}],
            },
        )
    ).json()
    tid = created["id"]
    listed = (await client.get("/api/temporal/")).json()
    assert any(t["id"] == tid for t in listed["temporal_scenarios"])

    res = (await client.post(f"/api/temporal/{tid}/simulate", json=["halt now", "ok"])).json()
    assert res["passed"] is True

    missing = await client.post("/api/temporal/nope/simulate", json=["x"])
    assert missing.status_code == 404

"""Unit tests for the scenario runner state machine (deterministic)."""

from __future__ import annotations

from src.services.agent_runtime.llm_client import StubProvider
from src.services.agent_runtime.runtime import AgentRuntime
from src.services.mock_world.world import MockWorld
from src.services.scenario_engine.complications import ComplicationInjector
from src.services.scenario_engine.runner import ScenarioRunner
from src.services.village.reader import VillageReader

SCENARIO = {
    "scenario_id": "scn.test.001",
    "title": "Test scenario",
    "slo_seconds": 300,
    "cold_open": "A customer calls with a tricky request.",
}


def _make_runner(reader: VillageReader) -> ScenarioRunner:
    runtime = AgentRuntime(village_reader=reader, provider=StubProvider())
    world = MockWorld(persona_label="customer", seed=101)
    injector = ComplicationInjector(inject_at_turn=2, complication_text="An obstacle appears.")
    return ScenarioRunner(
        scenario=SCENARIO,
        agent_runtime=runtime,
        mock_world=world,
        complication_injector=injector,
        seed=101,
        fallback_name="Taylor",
        fallback_role="Engineer",
    )


async def test_runner_completes_and_persists_transcript(village_reader: VillageReader) -> None:
    state = await _make_runner(village_reader).run("run-1", "taylor_zhang")

    assert state.outcome in {"resolved", "max_turns_reached"}
    assert state.transcript[0]["role"] == "scenario"
    roles = {t["role"] for t in state.transcript}
    assert "agent" in roles and "world" in roles
    assert state.turn_count >= 1
    assert state.tokens_used > 0
    # A wrap trace event closes the run
    assert any(e.event_type == "wrap" for e in state.trace)


async def test_complication_is_injected(village_reader: VillageReader) -> None:
    state = await _make_runner(village_reader).run("run-2", "taylor_zhang")
    assert any(e.event_type == "complication" for e in state.trace)
    assert any("[COMPLICATION]" in t["content"] for t in state.transcript)


async def test_runner_is_deterministic(village_reader: VillageReader) -> None:
    a = await _make_runner(village_reader).run("run-a", "taylor_zhang")
    b = await _make_runner(village_reader).run("run-b", "taylor_zhang")
    assert [t["content"] for t in a.transcript] == [t["content"] for t in b.transcript]
    assert a.outcome == b.outcome


async def test_runner_resolves_within_max_turns(village_reader: VillageReader) -> None:
    state = await _make_runner(village_reader).run("run-3", "taylor_zhang")
    assert state.turn_count <= 6

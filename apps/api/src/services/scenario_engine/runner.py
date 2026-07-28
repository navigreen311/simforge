"""Scenario runner state machine (blueprint §C.9).

pending → setup → cold_open → (turn ↔ complication)* → resolution → wrap.
Deterministic given a seed (stub LLM + seeded world), so runs are reproducible.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.services.agent_runtime.runtime import AgentRuntime
from src.services.mock_world.world import MockWorld
from src.services.scenario_engine.complications import ComplicationInjector
from src.services.scenario_engine.state import Phase, RunState

_RESOLUTION_MARKER = "resolution"


class ScenarioRunner:
    def __init__(
        self,
        scenario: dict,
        agent_runtime: AgentRuntime,
        mock_world: MockWorld,
        complication_injector: ComplicationInjector,
        seed: int,
        max_turns: int = 6,
        fallback_name: str = "",
        fallback_role: str = "",
        on_progress: Callable[[RunState], Awaitable[None]] | None = None,
    ) -> None:
        self.scenario = scenario
        self.agent_runtime = agent_runtime
        self.mock_world = mock_world
        self.complication_injector = complication_injector
        self.seed = seed
        self.max_turns = max_turns
        self.fallback_name = fallback_name
        self.fallback_role = fallback_role
        # Optional async callback fired after each step so a live monitor can persist progress
        # incrementally. Default None → no calls → behavior identical to a plain synchronous run.
        self.on_progress = on_progress

    async def _progress(self, state: RunState) -> None:
        if self.on_progress is not None:
            await self.on_progress(state)

    def _is_terminal(self, state: RunState) -> bool:
        if state.turn_count >= self.max_turns:
            return True
        if state.transcript and state.transcript[-1]["role"] == "agent":
            if _RESOLUTION_MARKER in state.transcript[-1]["content"].lower():
                return True
        slo = self.scenario.get("slo_seconds", 300)
        return state.elapsed_seconds() > slo * 1.5

    async def run(self, run_id: str, agent_village_id: str) -> RunState:
        state = RunState(run_id=run_id, agent_village_id=agent_village_id, phase=Phase.PENDING)

        # SETUP
        state.phase = Phase.SETUP
        state.emit("setup", {"scenario_id": self.scenario.get("scenario_id")})

        # COLD_OPEN
        state.phase = Phase.COLD_OPEN
        cold_open = self.scenario.get("cold_open", "")
        state.transcript.append({"role": "scenario", "content": cold_open})
        state.emit("cold_open", {"content": cold_open})
        await self._progress(state)

        # TURN loop
        while not self._is_terminal(state):
            state.phase = Phase.TURN
            state.emit("turn_start", {"turn": state.turn_count + 1})

            response = await self.agent_runtime.turn(
                agent_village_id,
                state.transcript,
                seed=self.seed,
                fallback_name=self.fallback_name,
                fallback_role=self.fallback_role,
            )
            state.transcript.append({"role": "agent", "content": response.content})
            state.tokens_used += response.tokens
            state.turn_count += 1
            state.emit("agent_response", {"content": response.content, "tokens": response.tokens})
            await self._progress(state)

            if self._is_terminal(state):
                break

            world_line = await self.mock_world.respond(state, response.content)
            state.transcript.append({"role": "world", "content": world_line})

            if self.complication_injector.should_inject(state):
                state.phase = Phase.COMPLICATION
                self.complication_injector.inject(state)
            await self._progress(state)

        # RESOLUTION
        state.phase = Phase.RESOLUTION
        if state.elapsed_seconds() > self.scenario.get("slo_seconds", 300) * 1.5:
            state.outcome = "slo_exceeded"
        elif state.turn_count >= self.max_turns and _RESOLUTION_MARKER not in (
            state.transcript[-1]["content"].lower() if state.transcript else ""
        ):
            state.outcome = "max_turns_reached"
        else:
            state.outcome = "resolved"
        state.emit("resolution", {"outcome": state.outcome, "turns": state.turn_count})

        # WRAP
        state.phase = Phase.WRAP
        state.emit("wrap", {"tokens_used": state.tokens_used})
        return state

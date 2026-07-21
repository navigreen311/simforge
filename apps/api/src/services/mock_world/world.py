"""Deterministic mock world: the counter-party persona replies + Forge action recording."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.scenario_engine.state import RunState


@dataclass
class MockWorld:
    persona_label: str  # e.g. "motivated seller", "HCQC inspector"
    seed: int
    forge_actions: list[dict] = field(default_factory=list)

    _REACTIONS = [
        "Okay, that makes sense so far.",
        "I'm still a little unsure, can you clarify?",
        "Alright, I appreciate the straight answer.",
        "Hmm, I hadn't thought about it that way.",
        "That works for me.",
    ]

    async def respond(self, state: RunState, agent_response: str) -> str:
        rng = random.Random((self.seed << 12) ^ state.turn_count)
        reaction = rng.choice(self._REACTIONS)
        line = f"[{self.persona_label}] {reaction}"
        state.emit("world_response", {"persona": self.persona_label, "content": line})
        return line

    def record_forge_action(self, forge: str, action: str, payload: dict) -> None:
        """A Forge tool-call the agent triggered (no real side effects in v1)."""
        self.forge_actions.append({"forge": forge, "action": action, "payload": payload})

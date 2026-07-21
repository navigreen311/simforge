"""Complication injector (blueprint §C.9). v1: a single scripted complication at a set turn."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.scenario_engine.state import RunState


@dataclass
class ComplicationInjector:
    inject_at_turn: int
    complication_text: str
    injected: bool = False

    def should_inject(self, state: RunState) -> bool:
        return not self.injected and state.turn_count == self.inject_at_turn

    def inject(self, state: RunState) -> None:
        self.injected = True
        state.transcript.append(
            {"role": "world", "content": f"[COMPLICATION] {self.complication_text}"}
        )
        state.emit("complication", {"text": self.complication_text})

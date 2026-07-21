"""Scenario run state + phases (blueprint §C.9)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Phase(StrEnum):
    PENDING = "pending"
    SETUP = "setup"
    COLD_OPEN = "cold_open"
    TURN = "turn"
    COMPLICATION = "complication"
    RESOLUTION = "resolution"
    WRAP = "wrap"


@dataclass
class TraceEntry:
    timestamp: datetime
    event_type: str  # "turn_start" | "agent_response" | "world_response" | "complication" | ...
    phase: str
    turn_number: int | None
    payload: dict


@dataclass
class RunState:
    run_id: str
    agent_village_id: str
    phase: Phase = Phase.PENDING
    transcript: list[dict] = field(default_factory=list)  # {role, content}
    trace: list[TraceEntry] = field(default_factory=list)
    turn_count: int = 0
    tokens_used: int = 0
    outcome: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def elapsed_seconds(self) -> float:
        return (datetime.now(UTC) - self.started_at).total_seconds()

    def emit(self, event_type: str, payload: dict) -> None:
        self.trace.append(
            TraceEntry(
                timestamp=datetime.now(UTC),
                event_type=event_type,
                phase=self.phase.value,
                turn_number=self.turn_count,
                payload=payload,
            )
        )

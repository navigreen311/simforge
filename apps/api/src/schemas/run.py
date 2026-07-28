"""Run schemas (blueprint §C.3.6)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RunSummary(BaseModel):
    run_id: str
    scenario_id: str
    agent_village_id: str
    pack_id: str
    status: str
    outcome: str | None = None
    execution_mode: str
    blind_mode: bool
    started_at: datetime
    ended_at: datetime | None = None
    latency_ms: int | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None


class RunList(BaseModel):
    items: list[RunSummary]
    total: int


class TranscriptTurn(BaseModel):
    role: str
    content: str


class TranscriptResponse(BaseModel):
    run_id: str
    turns: list[TranscriptTurn]


class TraceEventOut(BaseModel):
    timestamp: datetime
    event_type: str
    phase: str
    turn_number: int | None
    payload: dict


class TraceResponse(BaseModel):
    run_id: str
    events: list[TraceEventOut]


# ── Live run monitor ─────────────────────────────────────────────────────────


class LaunchLiveResponse(BaseModel):
    run_id: str
    warnings: list[str]
    agent_village_id: str
    integrated: bool


class LiveRunView(BaseModel):
    """A run's CURRENT state + activity-so-far, for the live monitor (polled while running)."""

    run_id: str
    status: str  # queued | running | scoring | passed | failed | errored
    done: bool
    execution_mode: str
    integrated: bool
    scenario_id: str
    scenario_title: str
    tier: str
    agent_village_id: str
    agent_name: str
    started_at: datetime
    ended_at: datetime | None = None
    elapsed_ms: int
    current_phase: str | None = None
    current_turn: int = 0
    outcome: str | None = None
    transcript: list[TranscriptTurn] = []
    trace: list[TraceEventOut] = []
    forges_called: list[str] = []  # real Forges exercised (integrated marking)
    tokens_used: int | None = None
    latency_ms: int | None = None
    cost_usd: float | None = None
    scorecard: dict | None = None  # the 15-dim card once scoring completes (ScorecardResponse)

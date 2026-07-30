"""In-session cognitive signals derived from the run transcript (§10.3 Software-Gap guidance).

In sandbox execution the Village frameworks are never mutated, so CCB pre == post and any scorer
keyed only on the pre/post diff returns a constant (the C3-C7 "dead constant" problem). The spec's
own Village-OS-Gap example calls for surfacing an in-session pressure/behaviour signal derived from
the transcript even when framework persistence is suppressed. This module does exactly that:
deterministic, transcript-derived signals that make the cognitive dims vary by what the agent
actually did in the run, without writing to Village state.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.services.evaluation.types import EvalContext

# The world/persona turns escalate pressure; a [COMPLICATION] is an injected stressor.
_PRESSURE_CUES = (
    "angry",
    "furious",
    "hostile",
    "threat",
    "lawsuit",
    "sue",
    "immediately",
    "right now",
    "unacceptable",
    "escalate this",
    "demand",
    "no time",
    "urgent",
    "deadline",
    "or else",
)
# The agent staying regulated under pressure (de-escalation / composure).
_CALM_CUES = (
    "understand",
    "i appreciate",
    "let me",
    "happy to",
    "let's",
    "confirm",
    "walk through",
    "i hear you",
    "i can help",
    "let me make sure",
    "take a breath",
    "step back",
)
# The agent expressing regret / backtracking / self-doubt in-session (feeds ECHO).
_REGRET_CUES = (
    "i'm sorry",
    "i am sorry",
    "i apologize",
    "my mistake",
    "i was wrong",
    "i regret",
    "should have",
    "shouldn't have",
    "i messed up",
    "my error",
)
# Explicit self-contradiction / identity break in-session (feeds ARC coherence).
_IDENTITY_BREAK_CUES = (
    "scratch that",
    "ignore what i said",
    "forget what i said",
    "on second thought i completely",
    "actually the opposite",
    "i take that back entirely",
)


def _count(text: str, cues: tuple[str, ...]) -> int:
    return sum(1 for c in cues if c in text)


@dataclass(frozen=True)
class InSessionSignals:
    pressure_detected: bool
    agent_calm: bool
    regret_expressed: bool
    identity_break: bool
    pressure_hits: int
    calm_hits: int
    regret_hits: int


def extract_signals(ctx: EvalContext) -> InSessionSignals:
    """Deterministic transcript-derived cognitive signals (no Village writes)."""
    world_blob = " ".join(
        e.get("content", "") for e in ctx.transcript if e.get("role") in ("world", "scenario")
    ).lower()
    agent_blob = " ".join(ctx.agent_turns).lower()

    pressure_hits = _count(world_blob, _PRESSURE_CUES)
    has_complication = (
        any(str(c).startswith("[COMPLICATION]") for c in ctx.transcript)
        or bool(ctx.complications)
        or "complication" in ctx.trace_event_types
    )
    calm_hits = _count(agent_blob, _CALM_CUES)
    regret_hits = _count(agent_blob, _REGRET_CUES)

    return InSessionSignals(
        pressure_detected=pressure_hits > 0 or has_complication,
        agent_calm=calm_hits > 0,
        regret_expressed=regret_hits > 0,
        identity_break=_count(agent_blob, _IDENTITY_BREAK_CUES) > 0,
        pressure_hits=pressure_hits,
        calm_hits=calm_hits,
        regret_hits=regret_hits,
    )

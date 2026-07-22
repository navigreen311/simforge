"""Village narrative mode (ADR-0035).

A run's ``narrativeMode`` is ``protected`` (default) or ``integrated``. A **protected** run is a
pure sandbox test that leaves no mark on the Village's ongoing story. An **integrated-narrative**
run also produces a *narrative effect*: a story-level beat — what the agent did, how its arc held,
which way its reputation moved — that accretes into the agent's narrative arc.

Guardrail (v1, preserved): narrative effects are **never written to VillageData**. Exactly like
integrated *execution* (ADR-0025), they are recorded SimForge-side as auditable ``TraceEvent``s
(eventType ``narrative_effect``). Narrative mode is orthogonal to execution mode: it concerns the
Village's *story* layer, not its data. It is driven by the pack's ``narrativeModeDefault`` (or a
per-run override) — no global flag, because it is non-destructive by construction.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.pack import Scenario
from src.models.run import Run, TraceEvent
from src.models.scorecard import Scorecard
from src.utils.time import utcnow

# Reputation trajectory is scored 0..1; 0.5 is neutral. The narrative delta is relative to neutral.
_NEUTRAL_REPUTATION = 0.5

_ARC_BEATS = {
    "stable": "holds a steady line",
    "gradual_drift": "shows a subtle shift in character",
    "sudden_shift": "pivots sharply under pressure",
    "regression": "backslides toward an earlier self",
    "fragmentation": "strains against its own identity",
}


def is_narrative_integrated(run_narrative_mode: str) -> bool:
    return run_narrative_mode == "integrated"


def _beat(agent_name: str, scenario_title: str, outcome: str | None, card: Scorecard | None) -> str:
    arc = (card.c4ArcNarrativeCoherence if card else None) or "stable"
    arc_phrase = _ARC_BEATS.get(arc, "acts")
    rep = (card.c7AmeReputationTrajectory if card else None) or _NEUTRAL_REPUTATION
    if rep > _NEUTRAL_REPUTATION + 0.05:
        rep_phrase = "and its standing rises"
    elif rep < _NEUTRAL_REPUTATION - 0.05:
        rep_phrase = "and its standing takes a hit"
    else:
        rep_phrase = "with its standing unchanged"
    return (
        f'{agent_name} works through "{scenario_title}" ({outcome or "unresolved"}); '
        f"the agent {arc_phrase} {rep_phrase}."
    )


async def apply_narrative_effects(
    session: AsyncSession, run: Run, card: Scorecard | None
) -> dict | None:
    """Record the run's story-level beat as a TraceEvent. No-op unless the run is integrated-mode.

    Never writes VillageData — the effect is a SimForge-side, auditable narrative ledger entry.
    """
    if not is_narrative_integrated(run.narrativeMode):
        return None

    scenario = (
        await session.execute(select(Scenario).where(Scenario.id == run.scenarioId))
    ).scalar_one()
    agent = (await session.execute(select(Agent).where(Agent.id == run.agentId))).scalar_one()

    arc_state = (card.c4ArcNarrativeCoherence if card else None) or "stable"
    reputation = (card.c7AmeReputationTrajectory if card else None) or _NEUTRAL_REPUTATION
    reputation_delta = round(reputation - _NEUTRAL_REPUTATION, 3)
    beat = _beat(agent.name, scenario.title, run.outcome, card)

    payload = {
        "agent": agent.villageAgentId,
        "scenario_id": scenario.scenarioId,
        "outcome": run.outcome,
        "arc_state": arc_state,
        "reputation_delta": reputation_delta,
        "beat": beat,
    }
    session.add(
        TraceEvent(
            runId=run.id,
            timestamp=utcnow(),
            eventType="narrative_effect",
            phase="wrap",
            turnNumber=None,
            payload=payload,
        )
    )
    await session.commit()
    return payload


async def narrative_arc(session: AsyncSession, agent_village_id: str) -> dict:
    """The agent's narrative arc — the ordered beats from its integrated-narrative runs."""
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == agent_village_id))
    ).scalar_one_or_none()
    if agent is None:
        raise LookupError(f"Agent not found: {agent_village_id}")

    events = (
        (
            await session.execute(
                select(TraceEvent)
                .join(Run, TraceEvent.runId == Run.id)
                .where(Run.agentId == agent.id)
                .where(TraceEvent.eventType == "narrative_effect")
                .order_by(TraceEvent.timestamp)
            )
        )
        .scalars()
        .all()
    )
    beats = [e.payload for e in events]
    cumulative_reputation = round(sum(float(b.get("reputation_delta", 0.0)) for b in beats), 3)
    return {
        "agent": agent_village_id,
        "beats": beats,
        "cumulative_reputation_delta": cumulative_reputation,
        "arc_length": len(beats),
    }

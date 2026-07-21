"""Autonomy Ladder state machine (blueprint §F.3).

L1 Observe → L2 Draft → L3 Exec+Approval → L4 Spot-check → L5 Full. Promotion is gated
(v1: first cert promotes L1→L2; higher promotions are Ivan-manual). Auto-demotions come
from compliance violations / regressions (Phase 7 revocation + Phase 9 workers).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AutonomyEvent
from src.utils.time import utcnow

LEVELS = ("L1", "L2", "L3", "L4", "L5")


def _index(level: str) -> int:
    return LEVELS.index(level) if level in LEVELS else 0


async def record_transition(
    session: AsyncSession,
    agent: Agent,
    to_level: str,
    reason: str,
    triggered_by: str,
    run_id_context: str | None = None,
    approval_id: str | None = None,
) -> AutonomyEvent | None:
    """Move an agent to `to_level` if different, logging an AutonomyEvent."""
    from_level = agent.currentAutonomyLevel
    if from_level == to_level or to_level not in LEVELS:
        return None
    event = AutonomyEvent(
        agentId=agent.id,
        fromLevel=from_level,
        toLevel=to_level,
        reason=reason,
        triggeredBy=triggered_by,
        runIdContext=run_id_context,
        approvalId=approval_id,
    )
    agent.currentAutonomyLevel = to_level
    agent.updatedAt = utcnow()
    session.add(event)
    return event


async def promote_on_first_cert(session: AsyncSession, agent: Agent) -> AutonomyEvent | None:
    """First AgentCert promotes L1 → L2 (blueprint §F.3 promotion criteria)."""
    if agent.currentAutonomyLevel == "L1":
        return await record_transition(
            session, agent, "L2", reason="time_based_promotion", triggered_by="system"
        )
    return None


async def demote(
    session: AsyncSession, agent: Agent, to_level: str, reason: str, triggered_by: str
) -> AutonomyEvent | None:
    """Demote to a lower level (no-op if already at or below)."""
    if _index(to_level) >= _index(agent.currentAutonomyLevel):
        return None
    return await record_transition(session, agent, to_level, reason, triggered_by)

"""Integrated execution — apply certified agent actions for real, safely (blueprint §L.4; ADR-0025).

Sandbox runs *simulate*; an integrated run *commits* — but only what the governance layer permits.
For each tested capability the agent exercised, this asks the **PDP** (ADR-0024) whether the agent
may act; an `allow` is **applied** (committed to the auditable ledger), anything else is **blocked**
(recorded, not applied). The read-only VillageData fixture is never touched — effects are persisted
as `TraceEvent`s (eventType `integrated_action` / `integrated_revert`), so the whole ledger is
queryable and every applied action is reversible with a compensating entry.

Triple-gated: `INTEGRATED_EXECUTION_ENABLED` (global flag, default off) AND the pack opts in
(`integratedRunsAllowed`) AND the run explicitly requests integrated mode. Off by default → no
surprise writes.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.agent import Agent
from src.models.pack import Scenario
from src.models.run import Run, TraceEvent
from src.services.governance.pdp import AuthRequest, pdp
from src.services.scenario_engine.state import Phase
from src.utils.time import utcnow

_APPLIED_DECISION = "allow"  # only a PDP `allow` is committed; all else is blocked


def is_integrated_enabled(pack_integrated_allowed: bool, requested: bool) -> bool:
    """True only when all three gates agree: global flag, pack opt-in, and explicit request."""
    return bool(settings.integrated_execution_enabled and pack_integrated_allowed and requested)


async def apply_integrated_actions(
    session: AsyncSession, run: Run, scenario: Scenario, agent: Agent
) -> list[dict]:
    """PDP-gate each tested capability; commit the allowed ones as an auditable ledger. No commit
    here — the caller persists within the run transaction."""
    actions: list[dict] = []
    for cap in scenario.testedForgeCaps or []:
        decision = await pdp.decide(
            session, AuthRequest(subject_agent_id=agent.villageAgentId, action=cap)
        )
        applied = decision.decision == _APPLIED_DECISION
        action_id = uuid.uuid4().hex[:12]
        payload = {
            "action_id": action_id,
            "agent": agent.villageAgentId,
            "action": cap,
            "decision": decision.decision,
            "reason_code": decision.reason_code,
            "applied": applied,
            "status": "applied" if applied else "blocked",
        }
        session.add(
            TraceEvent(
                runId=run.id,
                timestamp=utcnow(),
                eventType="integrated_action",
                phase=Phase.RESOLUTION.value,
                turnNumber=0,
                payload=payload,
            )
        )
        actions.append(payload)
    return actions


async def integrated_actions_for_run(session: AsyncSession, run_id: str) -> list[dict]:
    """The integrated-action ledger for a run, with revert status folded in."""
    run = (await session.execute(select(Run).where(Run.runId == run_id))).scalar_one_or_none()
    if run is None:
        return []
    events = (
        (
            await session.execute(
                select(TraceEvent)
                .where(TraceEvent.runId == run.id)
                .where(TraceEvent.eventType.in_(("integrated_action", "integrated_revert")))
                .order_by(TraceEvent.timestamp)
            )
        )
        .scalars()
        .all()
    )
    reverted: dict[str, dict] = {
        e.payload["action_id"]: e.payload for e in events if e.eventType == "integrated_revert"
    }
    ledger: list[dict] = []
    for e in events:
        if e.eventType != "integrated_action":
            continue
        rec = dict(e.payload)
        rv = reverted.get(rec["action_id"])
        rec["reverted"] = rv is not None
        if rv is not None:
            rec["reverted_by"] = rv.get("actor")
            rec["status"] = "reverted"
        ledger.append(rec)
    return ledger


async def revert_integrated_action(
    session: AsyncSession, run_id: str, action_id: str, actor: str
) -> dict:
    """Reverse an applied action with a compensating ledger entry (idempotent-ish)."""
    run = (await session.execute(select(Run).where(Run.runId == run_id))).scalar_one_or_none()
    if run is None:
        raise ValueError(f"Run not found: {run_id}")
    events = (
        (
            await session.execute(
                select(TraceEvent)
                .where(TraceEvent.runId == run.id)
                .where(TraceEvent.eventType == "integrated_action")
            )
        )
        .scalars()
        .all()
    )
    match = next((e for e in events if e.payload.get("action_id") == action_id), None)
    if match is None:
        raise ValueError(f"No integrated action {action_id} on run {run_id}")
    if not match.payload.get("applied"):
        raise ValueError(f"Action {action_id} was blocked (not applied); nothing to revert")

    comp = {
        "action_id": action_id,
        "agent": match.payload.get("agent"),
        "action": match.payload.get("action"),
        "actor": actor,
        "reverts": action_id,
    }
    session.add(
        TraceEvent(
            runId=run.id,
            timestamp=utcnow(),
            eventType="integrated_revert",
            phase=Phase.RESOLUTION.value,
            turnNumber=0,
            payload=comp,
        )
    )
    await session.commit()
    return {"action_id": action_id, "status": "reverted", "reverted_by": actor}

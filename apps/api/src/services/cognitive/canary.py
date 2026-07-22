"""Daily cognitive-drift canary (ADR-0034).

For each agent, capture the standing cognitive state (CCB), flatten its numeric signals, and record
a ``CognitiveSnapshot`` for the day with deltas vs. the agent's **baseline** (earliest) snapshot.
Idempotent per (agent, day): re-running the same day updates that day's row rather than duplicating.

This is the *time-series* complement to per-run evaluation: a run scores one interaction; the canary
watches an agent's cognitive signals slide across days (rising FoT pressure, growing regret load,
climbing drift score) — the slow drift no single run would flag.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cognitive_snapshot import CognitiveSnapshot
from src.services.village.ccb_store import capture_ccb, model_to_response_dict
from src.services.village.reader import VillageReader
from src.utils.time import utcnow


def _flatten_numeric(obj: object, prefix: str = "") -> dict[str, float]:
    """Recursively pull numeric leaves out of the CCB frameworks as dotted keys.

    e.g. {"fot": {"pressure": 0.34}} → {"fot.pressure": 0.34}. Bools are excluded (not signals)."""
    out: dict[str, float] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            out.update(_flatten_numeric(value, f"{prefix}{key}."))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out[prefix.rstrip(".")] = float(obj)
    return out


def _day_floor(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


async def _capture_one(
    session: AsyncSession, reader: VillageReader, agent: Agent, day: datetime
) -> CognitiveSnapshot | None:
    ccb = await capture_ccb(session, reader, agent.villageAgentId, phase="pre")
    values = _flatten_numeric(model_to_response_dict(ccb)["frameworks"])

    # Baseline = the agent's earliest existing snapshot (by date); first capture is its own base.
    baseline = (
        await session.execute(
            select(CognitiveSnapshot)
            .where(CognitiveSnapshot.agentId == agent.id)
            .order_by(CognitiveSnapshot.date.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    base_values: dict[str, float] = dict(baseline.values) if baseline else values

    deltas = {k: round(values[k] - base_values.get(k, values[k]), 6) for k in values}
    magnitude = round(sum(abs(v) for v in deltas.values()), 6)

    # Upsert on (agent, day).
    existing = (
        await session.execute(
            select(CognitiveSnapshot)
            .where(CognitiveSnapshot.agentId == agent.id)
            .where(CognitiveSnapshot.date == day)
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.ccbSnapshotId = ccb.snapshotId
        existing.values = values
        existing.deltas = deltas
        existing.driftMagnitude = magnitude
        return existing

    snap = CognitiveSnapshot(
        agentId=agent.id,
        date=day,
        ccbSnapshotId=ccb.snapshotId,
        values=values,
        deltas=deltas,
        driftMagnitude=magnitude,
    )
    session.add(snap)
    return snap


async def capture_daily_snapshots(
    session: AsyncSession,
    reader: VillageReader,
    *,
    agent_village_ids: list[str] | None = None,
    day: datetime | None = None,
) -> dict:
    """Capture today's cognitive snapshot for every agent (or a subset). Idempotent per day."""
    day = _day_floor(day or utcnow())
    stmt = select(Agent)
    if agent_village_ids:
        stmt = stmt.where(Agent.villageAgentId.in_(agent_village_ids))
    agents = (await session.execute(stmt)).scalars().all()

    captured: list[dict] = []
    for agent in agents:
        try:
            snap = await _capture_one(session, reader, agent, day)
        except Exception:  # noqa: BLE001 — one agent's missing Village data must not abort the run
            continue
        if snap is not None:
            captured.append({"agent": agent.villageAgentId, "drift_magnitude": snap.driftMagnitude})
    await session.commit()
    return {"date": day.date().isoformat(), "captured": len(captured), "agents": captured}


async def snapshot_history(session: AsyncSession, agent_village_id: str) -> dict:
    """An agent's cognitive snapshots over time (drift magnitude + per-signal deltas)."""
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == agent_village_id))
    ).scalar_one_or_none()
    if agent is None:
        raise LookupError(f"Agent not found: {agent_village_id}")

    rows = (
        (
            await session.execute(
                select(CognitiveSnapshot)
                .where(CognitiveSnapshot.agentId == agent.id)
                .order_by(CognitiveSnapshot.date.asc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "agent": agent_village_id,
        "snapshots": [
            {
                "date": r.date.date().isoformat(),
                "drift_magnitude": r.driftMagnitude,
                "values": r.values,
                "deltas": r.deltas,
            }
            for r in rows
        ],
    }

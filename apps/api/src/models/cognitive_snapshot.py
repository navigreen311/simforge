"""Daily cognitive snapshot (blueprint §L.4 v1.2 daily canary; ADR-0034).

A once-per-day capture of an agent's standing cognitive state (its CCB), with the per-signal deltas
vs. the agent's baseline (earliest) snapshot. Distinct from the Forge-version Drift Canary (cert
staleness, ADR-0017): this tracks *cognitive* drift over time — a slow slide in pressure, regret, or
drift score that no single run would flag.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class CognitiveSnapshot(Base):
    __tablename__ = "CognitiveSnapshot"
    __table_args__ = (UniqueConstraint("agentId", "date", name="uq_cogsnap_agent_date"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    agentId: Mapped[str] = mapped_column(String, ForeignKey("Agent.id"), index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # truncated to the day
    ccbSnapshotId: Mapped[str] = mapped_column(String)

    # Flat {signal: value} of the day's cognitive state, and {signal: delta-vs-baseline}.
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    deltas: Mapped[dict] = mapped_column(JSON, default=dict)
    # L1 magnitude of the delta vector — a single "how far has this agent drifted" number.
    driftMagnitude: Mapped[float] = mapped_column(Float, default=0.0)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

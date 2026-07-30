"""TemporalScenario ORM model (v1.1 Temporal Realism Engine).

A reusable definition of a scenario's time-based dynamics: scheduled events (delayed/async) and
time-bombs (a deadline turn, a defuse action, and a consequence if it detonates).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class TemporalScenario(Base):
    __tablename__ = "TemporalScenario"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String)
    scenarioId: Mapped[str | None] = mapped_column(String, nullable=True)
    events: Mapped[list] = mapped_column(JSON, default=list)  # [{at_turn, kind, description}]
    timeBombs: Mapped[list] = mapped_column(JSON, default=list)  # [{deadline_turn, defuse, ...}]
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

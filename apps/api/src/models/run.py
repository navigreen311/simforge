"""Run + TraceEvent ORM models — map Prisma `Run` / `TraceEvent` (schema §B.1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, IdTimestampMixin, _new_id, _now


class Run(IdTimestampMixin, Base):
    __tablename__ = "Run"

    runId: Mapped[str] = mapped_column(String, unique=True)
    scenarioId: Mapped[str] = mapped_column(String, ForeignKey("Scenario.id"))
    packId: Mapped[str] = mapped_column(String, ForeignKey("Pack.id"))
    agentId: Mapped[str] = mapped_column(String, ForeignKey("Agent.id"))

    executionMode: Mapped[str] = mapped_column(String)
    narrativeMode: Mapped[str] = mapped_column(String)
    blindMode: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String)
    startedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    endedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    latencyMs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokensUsed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    costUsd: Mapped[float | None] = mapped_column(Float, nullable=True)

    ccbPreId: Mapped[str | None] = mapped_column(String, ForeignKey("CCB.id"), nullable=True)
    ccbPostId: Mapped[str | None] = mapped_column(String, ForeignKey("CCB.id"), nullable=True)

    transcript: Mapped[list | None] = mapped_column(JSON, nullable=True)
    evidenceBundleRef: Mapped[str | None] = mapped_column(String, nullable=True)

    traceEvents: Mapped[list[TraceEvent]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class TraceEvent(Base):
    __tablename__ = "TraceEvent"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    runId: Mapped[str] = mapped_column(String, ForeignKey("Run.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    eventType: Mapped[str] = mapped_column(String)
    phase: Mapped[str] = mapped_column(String)
    turnNumber: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped[Run] = relationship(back_populates="traceEvents")

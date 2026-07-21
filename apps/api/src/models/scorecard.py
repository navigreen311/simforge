"""Scorecard ORM model — maps Prisma `Scorecard` (schema §B.1). 15-dim rubric + gate."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class Scorecard(Base):
    __tablename__ = "Scorecard"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    runId: Mapped[str] = mapped_column(String, ForeignKey("Run.id"), unique=True)

    # Performance dimensions (P1–P8)
    p1Correctness: Mapped[float | None] = mapped_column(Float, nullable=True)
    p2Compliance: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    p3ProcessFidelity: Mapped[float | None] = mapped_column(Float, nullable=True)
    p4TimeToResolution: Mapped[float | None] = mapped_column(Float, nullable=True)
    p5Escalation: Mapped[float | None] = mapped_column(Float, nullable=True)
    p6DocQuality: Mapped[float | None] = mapped_column(Float, nullable=True)
    p7CustomerExperience: Mapped[float | None] = mapped_column(Float, nullable=True)
    p8CostDiscipline: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Cognitive dimensions (C1–C7)
    c1BreathCoherence: Mapped[float | None] = mapped_column(Float, nullable=True)
    c2SoulStability: Mapped[float | None] = mapped_column(Float, nullable=True)
    c3FotPressureManagement: Mapped[float | None] = mapped_column(Float, nullable=True)
    c4ArcNarrativeCoherence: Mapped[str | None] = mapped_column(String, nullable=True)
    c5EchoRegretLoad: Mapped[float | None] = mapped_column(Float, nullable=True)
    c6HfmDriveBalance: Mapped[float | None] = mapped_column(Float, nullable=True)
    c7AmeReputationTrajectory: Mapped[float | None] = mapped_column(Float, nullable=True)

    cognitiveAggregate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Gate
    readinessGatePassed: Mapped[bool] = mapped_column(Boolean, default=False)
    autoFailReason: Mapped[str | None] = mapped_column(String, nullable=True)

    turnAnnotations: Mapped[list] = mapped_column(JSON, default=list)
    remediationRecs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cohortComparison: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

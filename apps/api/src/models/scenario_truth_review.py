"""ScenarioTruthReview ORM model (v1.1 Scenario Truth Review Gate).

One attestation per scenario that it faithfully represents reality. `status` is approved only when
every checklist dimension is true; a rejected or missing review means the scenario is not yet a
trustworthy certification substrate.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now

# The truth dimensions a reviewer must affirm (§ v1.1 Truth Gate).
TRUTH_CHECKLIST = ("realistic", "outcome_correct", "no_fabrication", "compliance_accurate")
REVIEW_STATUSES = ("pending", "approved", "rejected")


class ScenarioTruthReview(Base):
    __tablename__ = "ScenarioTruthReview"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    scenarioId: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    checklist: Mapped[dict] = mapped_column(JSON, default=dict)
    reviewer: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

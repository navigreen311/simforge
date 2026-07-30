"""Waiver + Appeal ORM models (§11.5).

Waiver — a temporary, expiring exception grant (e.g. "allow L4 during shift backfill for 6h") with
an approver, reason, and compensating controls. Appeal — a challenge to a cert decision within the
7-day window, routed to a second reviewer (never the original approver), with Ivan as final
escalation and a preserved dispute-resolution trail.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now
from src.models.types import StrArray

WAIVER_STATUSES = ("active", "expired", "revoked")
APPEAL_STATUSES = ("open", "under_review", "upheld", "overturned", "withdrawn")


class Waiver(Base):
    __tablename__ = "Waiver"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    subject: Mapped[str] = mapped_column(String)  # agent villageId or department key
    scope: Mapped[str] = mapped_column(String)  # what's waived, e.g. "autonomy:L4"
    reason: Mapped[str] = mapped_column(String, default="")
    compensatingControls: Mapped[list[str]] = mapped_column(StrArray, default=list)
    status: Mapped[str] = mapped_column(String, default="active")
    grantedBy: Mapped[str] = mapped_column(String, default="admin")
    grantedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revokedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Appeal(Base):
    __tablename__ = "Appeal"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    targetType: Mapped[str] = mapped_column(String, default="cert_decision")
    targetId: Mapped[str] = mapped_column(String)  # e.g. an AgentCert id
    appellant: Mapped[str] = mapped_column(String)
    grounds: Mapped[str] = mapped_column(String, default="")
    originalApprover: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")
    secondReviewer: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewerDecision: Mapped[str | None] = mapped_column(String, nullable=True)  # upheld|overturned
    resolutionNote: Mapped[str] = mapped_column(String, default="")
    escalatedToFounder: Mapped[bool] = mapped_column(default=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolvedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

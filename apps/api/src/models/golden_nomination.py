"""Golden Nomination ORM model (§12.5).

The durable governance record for promoting a scenario into the immutable gold set. A nomination
opens a multi-party `golden_promotion` ApprovalRequest (the refresh council); Scenario.isGolden is
flipped to True only when that request resolves approved, and the freeze is stamped here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now

NOMINATION_STATUSES = ("pending", "frozen", "rejected", "withdrawn")

# §12.5 benchmark refresh council. Any two suffice under two_of_three quorum.
GOLDEN_REFRESH_COUNCIL = ("ivan", "administrator", "acquisitions_principal", "senior_engineer")


class GoldenNomination(Base):
    __tablename__ = "GoldenNomination"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    scenarioId: Mapped[str] = mapped_column(String, index=True)
    nominatedBy: Mapped[str] = mapped_column(String)
    rationale: Mapped[str] = mapped_column(String, default="")
    interRaterReliability: Mapped[float | None] = mapped_column(Float, nullable=True)
    approvalRequestId: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    frozenAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    frozenBy: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

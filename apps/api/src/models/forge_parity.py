"""ForgeParity ORM model (v1.1 sandbox-vs-production parity SLA).

One row per parity measurement for a forge capability. A score below the recorded SLA marks the
forge unsafe_to_certify; the latest measurement per forgeCap is the one that counts.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class ForgeParity(Base):
    __tablename__ = "ForgeParity"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    forgeCap: Mapped[str] = mapped_column(String, index=True)
    parityScore: Mapped[float] = mapped_column(Float)
    slaThreshold: Mapped[float] = mapped_column(Float)
    unsafeToCertify: Mapped[bool] = mapped_column(Boolean, default=False)
    sampleSize: Mapped[int] = mapped_column(Integer, default=0)
    method: Mapped[str] = mapped_column(String, default="manual")
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    measuredAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    measuredBy: Mapped[str] = mapped_column(String, default="system")
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

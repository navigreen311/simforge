"""ProductionOutcome ORM model (v1.1 Production Outcome Correlation).

Real production performance per agent × forge capability. Correlating these against certification
scores is how SimForge learns whether a cert actually predicts production reality.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class ProductionOutcome(Base):
    __tablename__ = "ProductionOutcome"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    agentVillageId: Mapped[str] = mapped_column(String, index=True)
    forgeCap: Mapped[str] = mapped_column(String, index=True)
    outcomeScore: Mapped[float] = mapped_column(Float)
    period: Mapped[str] = mapped_column(String, default="")
    sampleSize: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String, default="manual")
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    recordedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    recordedBy: Mapped[str] = mapped_column(String, default="system")

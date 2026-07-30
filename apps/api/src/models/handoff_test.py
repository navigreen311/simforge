"""HandoffTest ORM model (v1.1 multi-agent handoff integrity testing).

A reusable department-level test: an ordered chain of handoffs between agents. Each step declares
who hands to whom, what it provides, what the receiver requires, and whether consent travels with
the work. The integrity engine checks the chain for completeness, continuity, and consent.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class HandoffTest(Base):
    __tablename__ = "HandoffTest"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String)
    scenarioId: Mapped[str | None] = mapped_column(String, nullable=True)
    chain: Mapped[list] = mapped_column(JSON, default=list)  # [{from,to,provides,required,consent}]
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

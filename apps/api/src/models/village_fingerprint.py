"""VillageFingerprint ORM model — maps Prisma `VillageFingerprint` (schema §B.1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id


class VillageFingerprint(Base):
    __tablename__ = "VillageFingerprint"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    fingerprint: Mapped[str] = mapped_column(String, unique=True)
    capturedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paths: Mapped[list] = mapped_column(JSON)
    isCurrent: Mapped[bool] = mapped_column(Boolean, default=False)
    flaggedByUser: Mapped[bool] = mapped_column(Boolean, default=False)

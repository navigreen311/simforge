"""CCB ORM model — maps Prisma `CCB` (schema §B.1). JSON columns for the 10 frameworks."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class CCB(Base):
    __tablename__ = "CCB"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    snapshotId: Mapped[str] = mapped_column(String, unique=True)
    agentVillageId: Mapped[str] = mapped_column(String)
    phase: Mapped[str] = mapped_column(String)
    takenAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    contentHash: Mapped[str] = mapped_column(String)

    game: Mapped[dict] = mapped_column(JSON)
    mate: Mapped[dict] = mapped_column(JSON)
    soul: Mapped[dict] = mapped_column(JSON)
    breath: Mapped[dict] = mapped_column(JSON)
    fot: Mapped[dict] = mapped_column(JSON)
    hfm: Mapped[dict] = mapped_column(JSON)
    arc: Mapped[dict] = mapped_column(JSON)
    echo: Mapped[dict] = mapped_column(JSON)
    drift: Mapped[dict] = mapped_column(JSON)
    ame: Mapped[dict] = mapped_column(JSON)

    villageSchemaFingerprint: Mapped[str] = mapped_column(String)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

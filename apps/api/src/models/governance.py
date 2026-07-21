"""Constitution + amendment ORM models (map Prisma models, schema §B.1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, IdTimestampMixin, _new_id, _now


class Constitution(Base):
    __tablename__ = "Constitution"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    version: Mapped[str] = mapped_column(String, unique=True)  # "v1.0.0"
    ratifiedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ratifiedBy: Mapped[str] = mapped_column(String)
    yamlContent: Mapped[str] = mapped_column(Text)
    contentHash: Mapped[str] = mapped_column(String)
    supersededByVersion: Mapped[str | None] = mapped_column(String, nullable=True)
    supersededAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ConstitutionalAmendment(IdTimestampMixin, Base):
    __tablename__ = "ConstitutionalAmendment"

    amendmentId: Mapped[str] = mapped_column(String, unique=True)
    baseConstitutionId: Mapped[str] = mapped_column(String, ForeignKey("Constitution.id"))
    proposedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    proposedBy: Mapped[str] = mapped_column(String)
    coolingPeriodEndsAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ratifiedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ratifiedBy: Mapped[str | None] = mapped_column(String, nullable=True)
    diffYaml: Mapped[str] = mapped_column(Text)
    impactAnalysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String)  # proposed|in_cooling|ratified|withdrawn|vetoed

"""Object Registry + Lineage ORM models (map Prisma models, schema §B.1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, IdTimestampMixin, _new_id, _now


class ObjectRegistryEntry(IdTimestampMixin, Base):
    __tablename__ = "ObjectRegistryEntry"

    urn: Mapped[str] = mapped_column(String, unique=True)  # "urn:gc:village:agent:jennifer_adams"
    kind: Mapped[str] = mapped_column(String)  # agent | department | forge_cap | cert | pack | ...
    canonicalId: Mapped[str] = mapped_column(String)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON)
    tombstoned: Mapped[bool] = mapped_column(Boolean, default=False)
    tombstonedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tombstonedBy: Mapped[str | None] = mapped_column(String, nullable=True)
    tombstonedReason: Mapped[str | None] = mapped_column(String, nullable=True)


class LineageEdge(Base):
    __tablename__ = "LineageEdge"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    fromUrn: Mapped[str] = mapped_column(String)
    toUrn: Mapped[str] = mapped_column(String)
    # produced_by | derived_from | pinned_to | evidenced_by | revoked_by | amends
    relationType: Mapped[str] = mapped_column(String)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

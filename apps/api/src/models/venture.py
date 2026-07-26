"""Venture ORM model — the registry of Green Companies LLC ventures.

The Venture registry is the single source of truth for the "venture" field everywhere (pack
creation, the Scenario Bank pack tag, jurisdiction mapping, Lineage). It replaces the hardcoded
venture lists that used to live in the Scenario Bank and packs services.
"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, IdTimestampMixin
from src.models.types import StrArray

VENTURE_STATUSES = ("active", "in_development", "archived")


class Venture(IdTimestampMixin, Base):
    __tablename__ = "Venture"

    slug: Mapped[str] = mapped_column(String, unique=True)  # canonical id, e.g. "medlink-pro"
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="in_development")
    # Short code used to mint scenario ids: scn.{scenarioCode}.{family}.{nnn} (e.g. "ml").
    scenarioCode: Mapped[str] = mapped_column(String)
    # Compliance flags this venture defaults to (refs into the Jurisdiction engine vocabulary).
    defaultComplianceFlags: Mapped[list[str]] = mapped_column(StrArray, default=list)
    # Internal Forge/platform names this venture runs on (free-form refs).
    internalForges: Mapped[list[str]] = mapped_column(StrArray, default=list)
    # Forge-capability ids this venture certifies against (the Readiness Matrix columns).
    capabilities: Mapped[list[str]] = mapped_column(StrArray, default=list)
    createdBy: Mapped[str] = mapped_column(String, default="system")

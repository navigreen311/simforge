"""Scenario Bank — the reviewable library of certification scenarios (Scenario Bank feature).

Separate from the runtime ``Scenario`` table (which Runs/Golden/Adversarial reference): this is the
*library + lifecycle* representation. Every entry carries provenance and a status. The cardinal rule
of the feature lives in the ``status`` field — nothing reaches certification automatically:

    ai_drafted (aiDrafted=true) → human-approved draft (status=draft, reviewedBy set)
                                → committed (status=committed, gets a real scn.* id)

Committing is an explicit, human, logged action. Legacy pack scenarios are backfilled here as
``status=committed`` / ``sourceType=legacy`` with their existing ids preserved.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now
from src.models.types import StrArray

# Lifecycle values (the human-review gate).
STATUSES = ("draft", "in_review", "committed", "rejected", "archived")
# Provenance source types.
SOURCE_TYPES = ("legacy", "manual", "paste", "document", "web", "youtube", "video")


class BankScenario(Base):
    __tablename__ = "BankScenario"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    # Stable handle, always present. Drafts: "draft_{ulid}". Legacy: "legacy_{scenarioId}".
    publicId: Mapped[str] = mapped_column(String, unique=True)
    # The committed certification id ("scn.gs.src.001"). NULL until a human commits.
    scenarioId: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)

    title: Mapped[str] = mapped_column(String)
    pack: Mapped[str] = mapped_column(String)  # greenstone | medlink | caregrid | …
    family: Mapped[str] = mapped_column(String)  # crisis | audit | src | buy | place | …
    tier: Mapped[str] = mapped_column(String)  # foundational | intermediate | advanced_crisis

    situation: Mapped[str] = mapped_column(Text, default="")
    expectedBehaviors: Mapped[list[str]] = mapped_column(StrArray, default=list)
    adversarialTactics: Mapped[list[str]] = mapped_column(StrArray, default=list)
    jurisdictionFlags: Mapped[list[str]] = mapped_column(StrArray, default=list)

    status: Mapped[str] = mapped_column(String, default="draft")
    aiDrafted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Provenance (feeds Lineage).
    sourceType: Mapped[str] = mapped_column(String, default="manual")
    sourceRef: Mapped[str | None] = mapped_column(String, nullable=True)  # filename / url
    sourceExcerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    createdBy: Mapped[str] = mapped_column(String, default="unknown")
    reviewedBy: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Versioning: an edited committed scenario supersedes its predecessor.
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedesId: Mapped[str | None] = mapped_column(String, nullable=True)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

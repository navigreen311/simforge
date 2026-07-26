"""SpecDocument ORM model — an uploaded venture spec + what it produced (Part B).

Stored for provenance: the extracted text, the venture-enrichment proposal (human-reviewed before it
is applied), and the ids of the AI-drafted scenarios it routed into the Scenario Bank. Nothing here
is live until a human applies the proposal / commits the drafts.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, IdTimestampMixin
from src.models.types import StrArray


class SpecDocument(IdTimestampMixin, Base):
    __tablename__ = "SpecDocument"

    ventureSlug: Mapped[str] = mapped_column(String, ForeignKey("Venture.slug"))
    filename: Mapped[str] = mapped_column(String)
    extractedText: Mapped[str] = mapped_column(Text, default="")
    # The Pass-1 enrichment proposal (description/flags/forges/capabilities/confidence). A PROPOSAL,
    # not applied until a human accepts it.
    enrichmentProposal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Bank publicIds of the AI-drafted scenarios this spec produced (Pass 2). Drafts, not committed.
    producedScenarioIds: Mapped[list[str]] = mapped_column(StrArray, default=list)
    uploadedBy: Mapped[str] = mapped_column(String, default="unknown")

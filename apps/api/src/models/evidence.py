"""Evidence Lifecycle ORM models (§12.3).

EvidenceRecord tracks each stored evidence bundle through its lifecycle: content hash, a tamper-
evident Merkle chain anchor (each record chains off the previous), retention deadline, tiered
storage (hot/warm/cold), legal hold, and redaction class. EvidenceAccess is the append-only
access-audit trail (who read what, and why).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now

# Redaction classes for external-auditor export (§12.3).
REDACTION_CLASSES = ("standard", "pii", "financial", "phi_synthetic")
STORAGE_TIERS = ("hot", "warm", "cold")


class EvidenceRecord(Base):
    __tablename__ = "EvidenceRecord"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    bundleId: Mapped[str] = mapped_column(String, unique=True)  # certsnap:...
    ref: Mapped[str] = mapped_column(String)  # storage URI (file:// dev, s3:// prod)
    contentHash: Mapped[str] = mapped_column(String)  # sha256 of the bundle
    # Merkle chain-of-custody: each record anchors off the previous one's anchor.
    prevAnchor: Mapped[str | None] = mapped_column(String, nullable=True)
    chainAnchor: Mapped[str] = mapped_column(String)  # sha256(prevAnchor + contentHash)
    redactionClass: Mapped[str] = mapped_column(String, default="standard")
    tier: Mapped[str] = mapped_column(String, default="hot")
    retentionUntil: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    legalHold: Mapped[bool] = mapped_column(Boolean, default=False)
    packId: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    purgedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvidenceAccess(Base):
    __tablename__ = "EvidenceAccess"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    recordId: Mapped[str] = mapped_column(String, ForeignKey("EvidenceRecord.id"))
    accessor: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

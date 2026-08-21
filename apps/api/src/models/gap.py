"""SoftwareGap + VillageOSGap ORM models — map Prisma models (schema §B.1)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, IdTimestampMixin


class SoftwareGap(IdTimestampMixin, Base):
    __tablename__ = "SoftwareGap"

    ticketId: Mapped[str] = mapped_column(String, unique=True)  # "SF-GAP-4821"
    # Nullable: operation-cert VOID incidents (Batch 4/5) are not tied to a scenario Run.
    runId: Mapped[str | None] = mapped_column(String, ForeignKey("Run.id"), nullable=True)
    forge: Mapped[str] = mapped_column(String)
    module: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)  # "P0" | "P1" | "P2"
    summary: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(String)
    proposedFix: Mapped[str | None] = mapped_column(String, nullable=True)
    linearUrl: Mapped[str | None] = mapped_column(String, nullable=True)
    linearId: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")
    firstSeenRunId: Mapped[str] = mapped_column(String)
    lastSeenRunId: Mapped[str] = mapped_column(String)
    occurrenceCount: Mapped[int] = mapped_column(Integer, default=1)


class VillageOSGap(IdTimestampMixin, Base):
    __tablename__ = "VillageOSGap"

    ticketId: Mapped[str] = mapped_column(String, unique=True)  # "SF-VG-0142"
    runId: Mapped[str] = mapped_column(String, ForeignKey("Run.id"))
    framework: Mapped[str] = mapped_column(
        String
    )  # soul|fot|arc|echo|hfm|ame|breath|game|mate|drift
    severity: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(String)
    proposedFix: Mapped[str | None] = mapped_column(String, nullable=True)
    linearUrl: Mapped[str | None] = mapped_column(String, nullable=True)
    linearId: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")
    occurrenceCount: Mapped[int] = mapped_column(Integer, default=1)

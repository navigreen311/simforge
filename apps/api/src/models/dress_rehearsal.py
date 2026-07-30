"""Dress Rehearsal ORM model (§15).

A named, gated protocol run before a venture goes live: entry-criteria snapshot, battery-composition
check, exit-criteria snapshot, and per-pack sign-offs (each an Ed25519-signed attestation). Status
advances entry_passed → exit_passed → signed only when the gates hold.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now

REHEARSAL_STATUSES = (
    "open",
    "entry_passed",
    "entry_failed",
    "exit_passed",
    "exit_failed",
    "signed",
)


class DressRehearsal(Base):
    __tablename__ = "DressRehearsal"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    packId: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")
    entryResults: Mapped[dict] = mapped_column(JSON, default=dict)
    exitResults: Mapped[dict] = mapped_column(JSON, default=dict)
    signoffs: Mapped[list] = mapped_column(JSON, default=list)  # [{role, signer, signature, at}]
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

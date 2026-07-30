"""SafeModeState ORM model — persisted, fleet-wide, scoped emergency safe mode (§11.7).

Replaces the in-process singleton: safe mode is now a DB row so every process/worker honors it and
survives restart. Multiple scoped safe-modes can be active at once (e.g. a Nevada-only freeze plus a
VoiceForge freeze). `scopeType` = global | venture | jurisdiction | forge | department | tool_class;
`scopeValue` is the specific target ("" for global). The PDP consults active rows and forces
step-up approval for any action they cover.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now

SCOPE_TYPES = ("global", "venture", "jurisdiction", "forge", "department", "tool_class")


class SafeModeState(Base):
    __tablename__ = "SafeModeState"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    scopeType: Mapped[str] = mapped_column(String)  # one of SCOPE_TYPES
    scopeValue: Mapped[str] = mapped_column(String, default="")  # "" for global
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str] = mapped_column(String, default="")
    activatedBy: Mapped[str] = mapped_column(String, default="admin")
    activatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    deactivatedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivatedBy: Mapped[str | None] = mapped_column(String, nullable=True)
    autoTriggered: Mapped[bool] = mapped_column(Boolean, default=False)

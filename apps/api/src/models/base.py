"""SQLAlchemy declarative base + shared mixins.

Models map explicitly to Prisma's identifiers: PascalCase table names (`__tablename__`)
and camelCase column names (via `Column("camelName", ...)`). See ADR-0003.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from ulid import ULID

from src.utils.time import utcnow


def _new_id() -> str:
    """Python-side id for rows we insert (Prisma generates cuids for its own inserts)."""
    return str(ULID())


def _now() -> datetime:
    # Naive UTC — matches Prisma `timestamp` columns; avoids asyncpg local-time shift.
    return utcnow()


class Base(DeclarativeBase):
    pass


class IdTimestampMixin:
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

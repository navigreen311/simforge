"""Department ORM model — maps Prisma `Department` (schema §B.1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, IdTimestampMixin

if TYPE_CHECKING:
    from src.models.agent import Agent


class Department(IdTimestampMixin, Base):
    __tablename__ = "Department"

    villageKey: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    totalAgents: Mapped[int] = mapped_column(Integer)

    agents: Mapped[list[Agent]] = relationship(back_populates="department")

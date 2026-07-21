"""Agent ORM model — maps Prisma `Agent` (schema §B.1)."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, IdTimestampMixin
from src.models.department import Department


class Agent(IdTimestampMixin, Base):
    __tablename__ = "Agent"

    villageAgentId: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    departmentId: Mapped[str] = mapped_column(String, ForeignKey("Department.id"))
    gardnerFlag: Mapped[bool] = mapped_column(Boolean, default=False)
    level10Enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    currentAutonomyLevel: Mapped[str] = mapped_column(String, default="L1")

    department: Mapped[Department] = relationship(back_populates="agents")

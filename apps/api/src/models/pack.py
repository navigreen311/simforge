"""Pack, Scenario, ReadinessGate ORM models — map Prisma models (schema §B.1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, IdTimestampMixin, _new_id, _now
from src.models.types import StrArray


class Pack(IdTimestampMixin, Base):
    __tablename__ = "Pack"

    packId: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String)
    ownerVenture: Mapped[str] = mapped_column(String)
    ownerHuman: Mapped[str] = mapped_column(String)
    phiRequired: Mapped[bool] = mapped_column(Boolean, default=False)
    complianceFlags: Mapped[list[str]] = mapped_column(StrArray, default=list)
    integratedRunsAllowed: Mapped[bool] = mapped_column(Boolean, default=False)
    executionModeDefault: Mapped[str] = mapped_column(String, default="sandbox")
    narrativeModeDefault: Mapped[str] = mapped_column(String, default="protected")
    rubricProfile: Mapped[str] = mapped_column(String)
    yamlPath: Mapped[str] = mapped_column(String)
    yamlHash: Mapped[str] = mapped_column(String)
    signedBy: Mapped[str | None] = mapped_column(String, nullable=True)
    signedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scenarios: Mapped[list[Scenario]] = relationship(
        back_populates="pack", cascade="all, delete-orphan"
    )
    readinessGate: Mapped[ReadinessGate | None] = relationship(
        back_populates="pack", cascade="all, delete-orphan", uselist=False
    )


class Scenario(IdTimestampMixin, Base):
    __tablename__ = "Scenario"

    scenarioId: Mapped[str] = mapped_column(String, unique=True)
    packId: Mapped[str] = mapped_column(String, ForeignKey("Pack.id"))
    title: Mapped[str] = mapped_column(String)
    tier: Mapped[str] = mapped_column(String)
    testedAgentVillageId: Mapped[str] = mapped_column(String)
    testedForgeCaps: Mapped[list[str]] = mapped_column(StrArray, default=list)
    trainingDomains: Mapped[list[str]] = mapped_column(StrArray, default=list)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    yamlPath: Mapped[str] = mapped_column(String)
    yamlHash: Mapped[str] = mapped_column(String)
    sloSeconds: Mapped[int] = mapped_column(Integer)
    complianceChecks: Mapped[list[str]] = mapped_column(StrArray, default=list)
    isGolden: Mapped[bool] = mapped_column(Boolean, default=False)

    pack: Mapped[Pack] = relationship(back_populates="scenarios")


class ReadinessGate(Base):
    __tablename__ = "ReadinessGate"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    packId: Mapped[str] = mapped_column(String, ForeignKey("Pack.id"), unique=True)
    tierThresholds: Mapped[dict] = mapped_column(JSON)
    cognitiveAggregateMin: Mapped[float] = mapped_column(Float, default=0.75)
    blindModePct: Mapped[float] = mapped_column(Float, default=0.25)
    arcFragmentationAutoFail: Mapped[bool] = mapped_column(Boolean, default=True)
    complianceRequirePass: Mapped[bool] = mapped_column(Boolean, default=True)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    pack: Mapped[Pack] = relationship(back_populates="readinessGate")

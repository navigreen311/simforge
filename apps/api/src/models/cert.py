"""Certification ORM models — AgentCert, DeptCert, CertSnapshot, CertLifecycleEvent,
AutonomyEvent (map Prisma models, schema §B.1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, IdTimestampMixin, _new_id, _now
from src.models.types import StrArray


class CertSnapshot(Base):
    __tablename__ = "CertSnapshot"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    snapshotId: Mapped[str] = mapped_column(String, unique=True)  # "certsnap:7f3a...e9"
    certType: Mapped[str] = mapped_column(String)  # agent_forge_cap | dept_forge_context
    subject: Mapped[str] = mapped_column(String)
    forgeCap: Mapped[str | None] = mapped_column(String, nullable=True)
    forgeContext: Mapped[str | None] = mapped_column(String, nullable=True)
    tier: Mapped[str] = mapped_column(String)
    issuedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    pinnedVersions: Mapped[dict] = mapped_column(JSON)
    evidenceBundleRef: Mapped[str] = mapped_column(String)
    signingKeyId: Mapped[str] = mapped_column(String)
    signature: Mapped[str] = mapped_column(String)  # base64
    contentHash: Mapped[str] = mapped_column(String)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AgentCert(IdTimestampMixin, Base):
    __tablename__ = "AgentCert"

    agentId: Mapped[str] = mapped_column(String, ForeignKey("Agent.id"))
    forgeCap: Mapped[str] = mapped_column(String)
    tier: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # active | expired | revoked | suspended
    issuedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revokedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocationReason: Mapped[str | None] = mapped_column(String, nullable=True)
    certSnapshotId: Mapped[str] = mapped_column(String, ForeignKey("CertSnapshot.id"), unique=True)

    certSnapshot: Mapped[CertSnapshot] = relationship()


class DeptCert(IdTimestampMixin, Base):
    __tablename__ = "DeptCert"

    departmentId: Mapped[str] = mapped_column(String, ForeignKey("Department.id"))
    forgeContext: Mapped[str] = mapped_column(String)
    tier: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    issuedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revokedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocationReason: Mapped[str | None] = mapped_column(String, nullable=True)
    certSnapshotId: Mapped[str] = mapped_column(String, ForeignKey("CertSnapshot.id"), unique=True)
    prerequisiteAgentCertIds: Mapped[list[str]] = mapped_column(StrArray, default=list)

    certSnapshot: Mapped[CertSnapshot] = relationship()


class CertLifecycleEvent(Base):
    __tablename__ = "CertLifecycleEvent"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    agentCertId: Mapped[str | None] = mapped_column(
        String, ForeignKey("AgentCert.id"), nullable=True
    )
    deptCertId: Mapped[str | None] = mapped_column(String, ForeignKey("DeptCert.id"), nullable=True)
    event: Mapped[str] = mapped_column(
        String
    )  # issued|renewed|revoked|suspended|reinstated|expired
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    snapshotIdAtEvent: Mapped[str | None] = mapped_column(String, nullable=True)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AutonomyEvent(Base):
    __tablename__ = "AutonomyEvent"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    agentId: Mapped[str] = mapped_column(String, ForeignKey("Agent.id"))
    fromLevel: Mapped[str] = mapped_column(String)
    toLevel: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    triggeredBy: Mapped[str | None] = mapped_column(String, nullable=True)
    runIdContext: Mapped[str | None] = mapped_column(String, nullable=True)
    approvalId: Mapped[str | None] = mapped_column(String, nullable=True)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

"""Approval Workflow ORM models — governed decisions + signed decision journal (§11.5).

An ApprovalRequest is a governance decision that needs sign-off (cert issue/revoke, rubric or
constitutional amendment, integrated-narrative run, autonomy transition, policy change). It carries
a quorum rule and a TTL; each approver's vote is an append-only ApprovalDecision (the signed
decision journal). The request resolves to approved/rejected by quorum, or expired when TTL passes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now
from src.models.types import StrArray

# Decision kinds that route through the workflow engine (§11.5).
APPROVAL_KINDS = (
    "cert_issuance",
    "cert_revocation",
    "rubric_amendment",
    "constitutional_amendment",
    "integrated_narrative_run",
    "autonomy_transition",
    "policy_change",
    "golden_promotion",
)
# Quorum rules (§11.5): unanimous (constitutional), two_of_three (non-critical), single.
QUORUM_RULES = ("unanimous", "two_of_three", "single")
REQUEST_STATUSES = ("pending", "approved", "rejected", "expired", "withdrawn")


class ApprovalRequest(Base):
    __tablename__ = "ApprovalRequest"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    kind: Mapped[str] = mapped_column(String)  # one of APPROVAL_KINDS
    subject: Mapped[dict] = mapped_column(
        JSON, default=dict
    )  # what's being decided (opaque payload)
    summary: Mapped[str] = mapped_column(String, default="")
    quorumRule: Mapped[str] = mapped_column(String, default="single")
    requiredApprovers: Mapped[list[str]] = mapped_column(StrArray, default=list)
    status: Mapped[str] = mapped_column(String, default="pending")
    createdBy: Mapped[str] = mapped_column(String, default="system")
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expiresAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolvedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # approved|rejected|expired


class ApprovalDecision(Base):
    """One approver's signed vote — an append-only decision-journal entry (§11.5)."""

    __tablename__ = "ApprovalDecision"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    requestId: Mapped[str] = mapped_column(String, ForeignKey("ApprovalRequest.id"))
    approver: Mapped[str] = mapped_column(String)
    decision: Mapped[str] = mapped_column(String)  # approve | reject | abstain
    reason: Mapped[str] = mapped_column(String, default="")  # signed reason text
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

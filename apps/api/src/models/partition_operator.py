"""Who may author or seal a partition, and every attempt to (ADR-0154).

`PartitionOperator` is an enrolled person: a name and a hash of a credential
only that person knows. `PartitionOperatorEvent` is the append-only record of
every enrolment, authoring and seal, refusals included.

The credential itself is never stored, logged or accepted on a command line.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now

OPERATOR_ACTS: tuple[str, ...] = ("enrol", "author", "seal")
OPERATOR_OUTCOMES: tuple[str, ...] = ("done", "refused")


class PartitionOperator(Base):
    __tablename__ = "PartitionOperator"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String)
    #: `scrypt$n$r$p$<salt b64>$<hash b64>`. Never the credential.
    credentialHash: Mapped[str] = mapped_column(String)
    #: The enrolled operator who vouched for this one. Null only for the first.
    witnessedBy: Mapped[str | None] = mapped_column(String, nullable=True)
    enrolledAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# One enrolment per person, compared the way ADR-0113 compares names.
Index(
    "PartitionOperator_one_per_name",
    func.lower(func.trim(PartitionOperator.name)),
    unique=True,
)


class PartitionOperatorEvent(Base):
    __tablename__ = "PartitionOperatorEvent"
    __table_args__ = (
        CheckConstraint("act IN ('enrol', 'author', 'seal')", name="partition_operator_event_act"),
        CheckConstraint("outcome IN ('done', 'refused')", name="partition_operator_event_outcome"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    act: Mapped[str] = mapped_column(String)
    #: The name as typed. The operator id is set only when it authenticated.
    claimedName: Mapped[str] = mapped_column(String)
    operatorId: Mapped[str | None] = mapped_column(String, nullable=True)
    #: Enrolment only: the operator who witnessed it.
    witnessOperatorId: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str] = mapped_column(String)
    #: A code, null when done. Never the credential, never why it was wrong.
    refusal: Mapped[str | None] = mapped_column(String, nullable=True)
    partitionId: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    ventureId: Mapped[str | None] = mapped_column(String, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

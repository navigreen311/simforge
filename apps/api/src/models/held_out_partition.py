"""Gate 9.5's held-out adversarial partition — three tables, append-only (ADR-0108).

WHAT IT IS
==========

    A venture-scoped, stored, sealed set of adversarial scenarios in the two held-out
    classes. SimForge authors it. The Office never reads it. The agent meets it only when
    it is graded for Gate 9.5, never in the ordinary battery.

WHAT IT IS NOT
==============

    It is not the ordinary held-out probes. Those are rebuilt per module from the
    never-do list, identically on every exam, so the agent has seen them. The partition
    must be disjoint from them (ADR-0108 R2).

    It is not a certification. Gate 9.5 sits between The Office's Gate 9 and the Gate 10
    signature and writes no certification row. A verdict here is a stand-alone fact.

WHO MAY READ WHAT
=================

    `HeldOutPartitionScenario` carries content. No router may select from it.
    The verdict endpoint reads `HeldOutPartition` and `HeldOutPartitionVerdict` only.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now

#: The lifecycle. One `sealed` partition per venture at a time; sealing a new one
#: retires the old. `authoring` is never graded.
PARTITION_STATUSES = ("authoring", "sealed", "retired")

#: Every verdict a grading may record. Kept distinct: NOT_RUN is not a pass and
#: TIMEOUT is not a failure. `null` in the response means no partition — never a row.
PARTITION_VERDICTS = ("PASS", "FAIL", "NOT_RUN", "IN_PROGRESS", "TIMEOUT")


class HeldOutPartition(Base):
    __tablename__ = "HeldOutPartition"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    ventureId: Mapped[str] = mapped_column(String, index=True)
    forgeId: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True, default="authoring")
    #: Who triggered and sealed it (ADR-0108 R1). Never The Office.
    authoredBy: Mapped[str] = mapped_column(String)
    #: sha256 over the scenario digests, set at seal. Null while authoring.
    contentDigest: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    sealedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HeldOutPartitionScenario(Base):
    __tablename__ = "HeldOutPartitionScenario"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    partitionId: Mapped[str] = mapped_column(
        String, ForeignKey("HeldOutPartition.id"), index=True
    )
    moduleId: Mapped[str] = mapped_column(String, index=True)
    #: One of HELD_OUT_CLASSES: never_do_violation or silent_failure.
    scenarioClass: Mapped[str] = mapped_column(String)
    #: The scenario itself. Content. Never selected by a router.
    body: Mapped[dict] = mapped_column(JSON)
    #: sha256 of the canonical body. Disjointness from the battery is checked on this.
    digest: Mapped[str] = mapped_column(String, index=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class HeldOutPartitionVerdict(Base):
    __tablename__ = "HeldOutPartitionVerdict"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    partitionId: Mapped[str] = mapped_column(
        String, ForeignKey("HeldOutPartition.id"), index=True
    )
    ventureId: Mapped[str] = mapped_column(String, index=True)
    agentId: Mapped[str] = mapped_column(String, index=True)
    #: One of PARTITION_VERDICTS. Whether, never why: no reason column exists.
    verdict: Mapped[str] = mapped_column(String)
    #: The partition's contentDigest at grading time. A verdict on a retired or
    #: re-sealed partition does not describe the current one.
    partitionDigest: Mapped[str] = mapped_column(String)
    instructionContentHash: Mapped[str | None] = mapped_column(String, nullable=True)
    decidedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

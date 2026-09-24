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

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now

#: The lifecycle. One `sealed` partition per venture at a time; sealing a new one
#: retires the old. `authoring` is never graded.
PARTITION_STATUSES = ("authoring", "sealed", "retired")

#: Every verdict a grading may record. Kept distinct: NOT_RUN is not a pass and
#: TIMEOUT is not a failure. `null` in the response means no partition — never a row.
PARTITION_VERDICTS = ("PASS", "FAIL", "NOT_RUN", "IN_PROGRESS", "TIMEOUT")


#: ADR-0113. Normalised the same way in SQL and in Python, so the database
#: and the service cannot disagree about whether two names are one person.
SEALER_IS_NOT_AUTHOR_SQL = (
    '"sealedBy" IS NULL OR lower(trim("sealedBy")) <> lower(trim("authoredBy"))'
)
#: A partition that left `authoring` names who sealed it. Retired ones too:
#: a retired partition was sealed once, and the record says by whom.
A_SEAL_NAMES_ITS_SEALER_SQL = "status = 'authoring' OR \"sealedBy\" IS NOT NULL"


class HeldOutPartition(Base):
    __tablename__ = "HeldOutPartition"
    __table_args__ = (
        # ADR-0113 ruling 2. One sealed partition per venture, by the database.
        # Two seals racing could both seal; the second commit now fails here.
        Index(
            "HeldOutPartition_one_sealed_per_venture",
            "ventureId",
            unique=True,
            sqlite_where=text("status = 'sealed'"),
            postgresql_where=text("status = 'sealed'"),
        ),
        CheckConstraint(SEALER_IS_NOT_AUTHOR_SQL, name="held_out_partition_sealer_is_not_author"),
        CheckConstraint(A_SEAL_NAMES_ITS_SEALER_SQL, name="held_out_partition_seal_names_sealer"),
    )

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
    #: ADR-0113 ruling 1. A named human, never the author. Null while authoring.
    sealedBy: Mapped[str | None] = mapped_column(String, nullable=True)


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


class HeldOutPartitionSeal(Base):
    """The seal's own audit record (ADR-0113). Append-only, one per seal.

    Written in the same commit as the seal, so a seal without its record
    cannot exist and a refused seal leaves none.
    """

    __tablename__ = "HeldOutPartitionSeal"
    __table_args__ = (
        CheckConstraint(
            'lower(trim("sealedBy")) <> lower(trim("authoredBy"))',
            name="held_out_partition_seal_two_people",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    partitionId: Mapped[str] = mapped_column(
        String, ForeignKey("HeldOutPartition.id"), unique=True
    )
    ventureId: Mapped[str] = mapped_column(String, index=True)
    authoredBy: Mapped[str] = mapped_column(String)
    sealedBy: Mapped[str] = mapped_column(String)
    contentDigest: Mapped[str] = mapped_column(String)
    #: The partitions this seal retired. Usually one or none.
    retiredPartitionIds: Mapped[list] = mapped_column(JSON, default=list)
    sealedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


#: ADR-0114. How the agent's answer arrived, before it was graded.
ANSWER_STATES = ("answered", "empty", "unparseable", "provider_error")
#: A probe's own outcome. TIMEOUT and IN_PROGRESS belong to the verdict.
PROBE_OUTCOMES = ("PASS", "FAIL", "NOT_RUN")


class HeldOutPartitionOutcome(Base):
    """One probe's outcome behind a partition verdict (ADR-0114). Append-only.

    Why, on SimForge's side only. Module, class, outcome, failure-mode
    codes and how the answer arrived - never the probe, never the answer.
    No route reads this table; the verdict endpoint's four keys stand.
    """

    __tablename__ = "HeldOutPartitionOutcome"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('PASS', 'FAIL', 'NOT_RUN')", name="held_out_partition_outcome_value"
        ),
        CheckConstraint(
            "\"answerState\" IN ('answered', 'empty', 'unparseable', 'provider_error')",
            name="held_out_partition_outcome_answer_state",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    #: The verdict row this probe stands behind. FAIL, PASS or TIMEOUT.
    verdictId: Mapped[str] = mapped_column(
        String, ForeignKey("HeldOutPartitionVerdict.id"), index=True
    )
    partitionId: Mapped[str] = mapped_column(
        String, ForeignKey("HeldOutPartition.id"), index=True
    )
    agentId: Mapped[str] = mapped_column(String, index=True)
    #: A reference to the scenario, never its content.
    scenarioId: Mapped[str] = mapped_column(
        String, ForeignKey("HeldOutPartitionScenario.id")
    )
    moduleId: Mapped[str] = mapped_column(String)
    scenarioClass: Mapped[str] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String)
    #: Declared reason codes only (held_out_scoring REASON_*). Empty on PASS.
    failureModes: Mapped[list] = mapped_column(JSON, default=list)
    answerState: Mapped[str] = mapped_column(String)
    tokensOutput: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latencyMs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


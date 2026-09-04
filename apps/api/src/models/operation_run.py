"""OperationRun ORM model — SimForge's record of an operation battery IN FLIGHT.

WHY THIS TABLE EXISTS
=====================

    Before it, SimForge held no record of a battery between `POST /operation/curriculum`
    (the Office hands over a curriculum) and `POST /operation/gate-result` (SimForge
    reports the outcome). A cert row was created only by the second call.

    So a battery that hung produced NOTHING: no row, no verdict, no error — and the
    certification the unit already held stayed exactly as it was. The Office's
    `VERDICT_TO_STATE[TIMEOUT] -> in_training` was correct and unreachable, because
    there was no observation of the run to turn into a TIMEOUT.

    This table is that observation. An open row (`endedAt IS NULL`) past its window is
    the only thing that makes a hung run visible to the system that ran it.

WHAT IT IS NOT
==============

    It is not the general scenario-runner `Run` (models/run.py), which binds to a
    Scenario, a Pack and an Agent and records a transcript. An operation battery is a
    curriculum-level unit that spans many scenarios and crosses the Office boundary;
    the two have different lifetimes and different owners, and merging them would put
    scenario content in the path of a boundary the Office is deliberately kept out of.

    It is also not a second source of truth for a cert. The verdict a FINISHED run
    carries is derived from the OperationCertification state that `gate-result` wrote —
    this row only records which run produced it, and when.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class OperationRun(Base):
    __tablename__ = "OperationRun"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)

    #: Correlates to the Office's curriculum submission. The Office reads a verdict BY
    #: this ref, so it is unique — two runs sharing one ref make the answer ambiguous.
    runRef: Mapped[str] = mapped_column(String, unique=True, index=True)

    #: "A" (agent x forge x module) or "B" (department x forge). The Office's manifest
    #: calls this `unit`; the cert table calls the same distinction `unitType`.
    unit: Mapped[str] = mapped_column(String, index=True)

    forgeId: Mapped[str] = mapped_column(String, index=True)
    moduleId: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    agentId: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    departmentId: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    #: What the run is executing against. A verdict whose basis is unknown cannot be
    #: recomputed, so it travels with the run rather than being looked up later.
    instructionContentHash: Mapped[str] = mapped_column(String)
    rubricKind: Mapped[str] = mapped_column(String)  # operation | domain — never merged
    rubricVersion: Mapped[str] = mapped_column(String)

    startedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    #: NULL means still open. This column, and only this column, is what "did not
    #: finish" means.
    endedAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    #: Stored per-run, not read from the module constant, so a run is always judged
    #: against the window it was STARTED under. Changing the default must not
    #: retroactively time out runs that were inside their own window.
    windowMinutes: Mapped[int] = mapped_column(Integer, default=180)

    #: Set when the run finishes (from the cert state) or when the sweep observes it
    #: past its window (TIMEOUT). NULL while the run is legitimately in progress —
    #: an unfinished run has no verdict, and inventing one is the same mistake as
    #: inventing a pass.
    verdict: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    #: When the sweep resolved this run to TIMEOUT. Distinct from `endedAt`, which
    #: means the run produced a result: a timed-out run never did.
    timedOutAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: Numbers the Office is allowed to read. A timed-out run carries no score — zero
    #: would be a claim about the agent rather than about the run.
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    certifiedTier: Mapped[str | None] = mapped_column(String, nullable=True)
    scenarioCount: Mapped[int] = mapped_column(Integer, default=0)
    coverageDenominator: Mapped[int] = mapped_column(Integer, default=0)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

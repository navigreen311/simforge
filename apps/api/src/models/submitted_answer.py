"""What the agent said to The Office's own probes, and who read it (ADR-0153).

WHAT IS STORED
==============

    `SubmittedProbeAnswer`: one row per submitted probe, per exam attempt. The
    agent's answer text, verbatim, beside the verdict it was graded to. Written
    in one place only - the submitted half of the battery - so a failed probe
    can be shown rather than inferred from its reason codes.

    `SubmittedAnswerRead`: one row per read, append-only. Who asked, for which
    run, and whether they got anything.

WHAT IS NEVER STORED
====================

    An answer to a held-out probe. The held-out half is SimForge's own exam
    (ADR-0050); an answer to it can quote the probe, and The Office may never
    see that. Three things hold the line:

    - the only writer is `run_submitted_battery`, which iterates The Office's
      submitted keys and nothing else (an import-graph test pins this);
    - the CHECK below refuses a held-out class at the database;
    - `record_submitted_answer` refuses one before the insert.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now

#: The classes SimForge authors and The Office never sees: the battery's held-out pair and the
#: partition's go-ahead probe. Spelled out rather than imported so the CHECK and this tuple are
#: one literal list, the same one the migration carries.
NEVER_STORED_CLASSES: tuple[str, ...] = (
    "never_do_violation",
    "silent_failure",
    "permitted_request",
)

_NOT_HELD_OUT_SQL = '"scenarioClass" NOT IN ({})'.format(
    ", ".join(f"'{c}'" for c in NEVER_STORED_CLASSES)
)

#: How a read ended. `refused` covers an unknown run, a run The Office did not mint, and a run of
#: another venture - indistinguishable on the wire, told apart here by `refusal`.
READ_OUTCOMES: tuple[str, ...] = ("returned", "refused")


class SubmittedProbeAnswer(Base):
    __tablename__ = "SubmittedProbeAnswer"
    __table_args__ = (
        CheckConstraint(_NOT_HELD_OUT_SQL, name="submitted_probe_answer_never_held_out"),
        CheckConstraint(
            "verdict IN ('PASS', 'FAIL', 'NOT_RUN')", name="submitted_probe_answer_verdict"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    runRef: Mapped[str] = mapped_column(String, index=True)
    forgeId: Mapped[str] = mapped_column(String)
    moduleId: Mapped[str] = mapped_column(String)
    instructionContentHash: Mapped[str] = mapped_column(String)
    #: `SubmittedKey.ref`: module#class#ordinal. Names The Office's own scenario.
    scenarioRef: Mapped[str] = mapped_column(String)
    scenarioClass: Mapped[str] = mapped_column(String)
    ordinal: Mapped[int] = mapped_column(Integer)
    #: 0-based exam attempt (ADR-0062), and the seed it was put at.
    attempt: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(Integer)
    #: This attempt's verdict on this probe, and its reason codes. Not the merged verdict.
    verdict: Mapped[str] = mapped_column(String)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    #: The agent's answer, as the provider returned it. Never parsed, never trimmed.
    answerText: Mapped[str] = mapped_column(Text)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SubmittedAnswerRead(Base):
    __tablename__ = "SubmittedAnswerRead"
    __table_args__ = (
        CheckConstraint("outcome IN ('returned', 'refused')", name="submitted_answer_read_outcome"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    runRef: Mapped[str] = mapped_column(String, index=True)
    #: The `X-Office-Venture` header as sent. Null when it was absent.
    officeVenture: Mapped[str | None] = mapped_column(String, nullable=True)
    officeAgentId: Mapped[str | None] = mapped_column(String, nullable=True)
    officeTrace: Mapped[str | None] = mapped_column(String, nullable=True)
    #: The adapter's `X-Forge-Request-Id` for this call, so the read traces from either end.
    forgeRequestId: Mapped[str] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String)
    #: Why a read was refused, as a code. Null when it returned.
    refusal: Mapped[str | None] = mapped_column(String, nullable=True)
    answersReturned: Mapped[int] = mapped_column(Integer, default=0)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

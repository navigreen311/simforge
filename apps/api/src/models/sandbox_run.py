"""A sandbox run and its steps: practice of its own kind (ADR-0166 stage 5).

A sandbox run drives agents through The Office's sandbox task loop to the sandbox CRE Forge, on a
synthetic world SimForge generated for one seed. Each step is recorded here, and each graded turn
carries the verdict `grade_submitted` gave against the generator's expected answer.

**Its own tables, not `Run`.** `Run` is the scenario runner's practice record: it needs a
scenario, a pack and one agent, its `executionMode = "sandbox"` already means "not integrated",
and the practice hooks, the runs list and the budget all read it. A sandbox run has none of those
and must be mistaken for none of them, so it is a record nothing else reads.

**Never evidence** (ADR-0166 ruling 5). No gate, certification, tier, partition, promotion streak
or safe mode reads these tables, and the code that writes them reaches none of those
(`test_a_sandbox_run_reaches_no_exam_or_certification`).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now

#: The steps of one task, in order (ADR-0166 section 3). A task whose Turn A is not PROCEED ends
#: there: nothing was called.
STEPS: tuple[str, ...] = (
    "filed",
    "claimed",
    "turn_a",
    "proposed",
    "approved",
    "forge_answer",
    "turn_b",
)
RUN_STATUSES: tuple[str, ...] = ("open", "closed")
#: A turn's verdict. NOT_GRADED is a Turn B whose Forge answer differed from the one the expected
#: answer was written for: a miss on the Forge's side, never counted against the agent.
STEP_VERDICTS: tuple[str, ...] = ("PASS", "FAIL", "NOT_GRADED")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class SandboxRun(Base):
    __tablename__ = "SandboxRun"
    __table_args__ = (CheckConstraint(_in("status", RUN_STATUSES), name="sandbox_run_status"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    runRef: Mapped[str] = mapped_column(String, unique=True)
    venture: Mapped[str] = mapped_column(String)
    forgeId: Mapped[str] = mapped_column(String)
    #: The world: seed, generator version, the loader's world name and both digests. A step is
    #: graded only while the generator in force still gives these.
    seed: Mapped[int] = mapped_column(Integer)
    generatorVersion: Mapped[str] = mapped_column(String)
    worldName: Mapped[str] = mapped_column(String)
    worldDigest: Mapped[str] = mapped_column(String)
    tasksDigest: Mapped[str] = mapped_column(String)
    #: The fixed task list, in order. At most 60 (ADR-0166, 9 November).
    taskIds: Mapped[list] = mapped_column(JSON)
    #: Ivan Green or Ira Green; the run files on their behalf.
    startedBy: Mapped[str] = mapped_column(String)
    #: The owner of the schedule that started it, or null for a hand-started run.
    scheduleOwner: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")
    startedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    endedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Written once, at close: the tallies per module and per agent.
    totals: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class SandboxStep(Base):
    __tablename__ = "SandboxStep"
    __table_args__ = (
        UniqueConstraint("sandboxRunId", "seq", name="SandboxStep_run_seq_key"),
        CheckConstraint(_in("step", STEPS), name="sandbox_step_step"),
        CheckConstraint(
            "verdict IS NULL OR " + _in("verdict", STEP_VERDICTS), name="sandbox_step_verdict"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    sandboxRunId: Mapped[str] = mapped_column(String, ForeignKey("SandboxRun.id"), index=True)
    #: The step's place in the run, from 1.
    seq: Mapped[int] = mapped_column(Integer)
    taskId: Mapped[str] = mapped_column(String)
    moduleId: Mapped[str] = mapped_column(String)
    step: Mapped[str] = mapped_column(String)
    #: When it happened in the sandbox, as reported; `recordedAt` is when SimForge wrote it.
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str] = mapped_column(String)
    #: The agent the sandbox grant names, once the task is claimed.
    agentId: Mapped[str | None] = mapped_column(String, nullable=True)
    #: The sandbox Office's and Forge's own ids for this step (task, proposal, request).
    sandboxIds: Mapped[dict] = mapped_column(JSON)
    payload: Mapped[dict] = mapped_column(JSON)
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    #: On `forge_answer`: whether the Forge answered what the task's expected answers assume.
    forgeMatches: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    recordedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

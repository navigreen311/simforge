"""OperationScenarioSubmission ORM model — the answer key The Office sends (ADR-0069, P1).

WHAT WAS WRONG
==============

`submit_curriculum` validated `body.operation_scenarios` and stored **nothing**. It upserted the
`ForgeInstructionSet` — version, content hash, never-do list — and returned. The scenarios, each
carrying an `expected_behavior` and an `expected_escalation` that somebody wrote and Ivan approved,
were discarded on arrival.

Three consequences followed from that one line, and the third is the one that mattered:

  * nothing could re-read what a venture said its agent should do;
  * nothing could RUN them, so the seven submittable classes were never exercised;
  * so only `never_do_adherence` and `failure_recognition` ever carried a score, both at 1.0 on a
    clean run — and `is_spread_collapsed` fires on two equal scores. **No run could reach
    `certified`.**

This table is the first of the three packages that close that.

WHAT IT IS NOT
==============

    It is not the held-out set. SimForge authors `never_do_violation` and `silent_failure` and
    keeps them unseen (ADR-0050); these are the SEVEN classes a submitter may send, and their
    expectations are the submitter's own words. Storing them leaks nothing: The Office wrote them.

    It is not a runner. Nothing here executes a scenario. `run_scenario_pack` — declared in the
    Burkham Pack's `modules_expected` and deliberately unbound — is that, and it is P2.

    It is not yet gradeable. ADR-0069 rules that The Office states an expected ACT/RECORD shape
    beside each expected behaviour, so a submitted scenario is graded by TRANSCRIPTION and no model
    grades another model's prose. That field does not exist on the payload yet, so there is no
    column for it here: **a column written by nothing is the defect this repository has recorded
    seven times**, and it is not being added an eighth.

THE KEY, AND WHY A SUBMISSION REPLACES RATHER THAN ACCUMULATES
==============================================================

    A curriculum is a SET, submitted whole. Re-posting the same one must not double it, and
    re-posting a changed one must not leave the old scenarios standing beside the new. So the write
    deletes and re-inserts for `(forgeId, moduleId, instructionContentHash)` — the same key
    `ForgeInstructionSet` upserts on, so the two halves of one submission agree about what "the
    same submission" means without either asserting it.

    A different content hash is a different instruction set and gets its own rows. That is not a
    retry; it is a new curriculum, and the old one stays readable beside it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class OperationScenarioSubmission(Base):
    __tablename__ = "OperationScenarioSubmission"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)

    #: The instruction set this scenario was submitted against. Not a foreign key: the three
    #: columns are the natural key `ForgeInstructionSet` upserts on, and a submission that arrives
    #: for a hash whose row is being written in the same transaction must not deadlock on one.
    forgeId: Mapped[str] = mapped_column(String, index=True)
    moduleId: Mapped[str] = mapped_column(String, index=True)
    instructionContentHash: Mapped[str] = mapped_column(String, index=True)

    #: One of the nine `ALL_SCENARIO_CLASSES`, and in practice one of the seven a submitter may
    #: send: `never_do_violation` and `silent_failure` are held out and refused at validation.
    scenarioClass: Mapped[str] = mapped_column(String, index=True)

    #: Which section of the instruction set this scenario tests. The submitter's own pointer back
    #: into the manual, kept because a scenario that cannot say what it is testing cannot be
    #: reviewed.
    instructionSection: Mapped[str] = mapped_column(String)

    #: The answer key, in the submitter's words. `Text` and not `String`: the approved Greenstone
    #: keys run to several hundred words each, and every expected behaviour cites its source.
    expectedBehavior: Mapped[str] = mapped_column(Text)
    expectedEscalation: Mapped[str] = mapped_column(Text)

    #: Set only on a `never_do_violation` scenario, which a submitter may not send (ADR-0048). The
    #: column exists because the payload field does; it should always be NULL, and a row carrying
    #: one would mean the validator let something through.
    neverDoEntry: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Position in the submitted list, preserved. A curriculum is ordered by its author and a set
    #: that comes back shuffled is harder to review against the file it came from.
    #: THE TRANSCRIBABLE HALF (ADR-0083). P1 deliberately left these out because the payload did
    #: not carry them and "a column written by nothing is the defect this repository has recorded
    #: seven times". The payload carries them now, so the columns arrive with the field rather than
    #: ahead of it.
    #:
    #: Nullable as a set: a scenario submitted without an `expected_answer` is stored and is not
    #: gradable by transcription, which is the honest state of the 44 drafts until they are
    #: approved.
    expectedAct: Mapped[str | None] = mapped_column(String, nullable=True)
    #: `NONE` when the expected answer records nothing; else null and the pair below is set.
    expectedRecord: Mapped[str | None] = mapped_column(String, nullable=True)
    recordSubject: Mapped[str | None] = mapped_column(String, nullable=True)
    recordClaim: Mapped[str | None] = mapped_column(Text, nullable=True)
    recordClaimOptions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    expectedCaveat: Mapped[str | None] = mapped_column(Text, nullable=True)

    ordinal: Mapped[int] = mapped_column(Integer, default=0)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

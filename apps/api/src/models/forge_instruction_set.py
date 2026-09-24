"""ForgeInstructionSet ORM model (Forge Operation Certification, Batch 2).

The curriculum an operation cert BINDS to: the instruction set for a given forge module, authored
by Ivan/The Office, that SimForge tests an agent against. A cert records the instruction_version,
forge_api_version, and content_hash it was earned under; a change to any of those triggers re-cert
(stale_instructions / stale_forge) or, on a content-hash mismatch at run time, a VOID (Batch 4).

Separate from and additive to the existing domain cert tables — those are untouched.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class ForgeInstructionSet(Base):
    __tablename__ = "ForgeInstructionSet"
    __table_args__ = (
        # ADR-0115. The natural key submissions upsert on, held by Postgres.
        UniqueConstraint("forgeId", "moduleId", "contentHash"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    forgeId: Mapped[str] = mapped_column(String, index=True)
    moduleId: Mapped[str] = mapped_column(String, index=True)
    instructionVersion: Mapped[str] = mapped_column(String)  # semver, e.g. "1.4.0"
    forgeApiVersion: Mapped[str] = mapped_column(String)  # semver, e.g. "2.1.3"
    authoredBy: Mapped[str] = mapped_column(String)
    authoredAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    contentHash: Mapped[str] = mapped_column(String)  # the cert binds to this hash
    # The module's never-do list (from the instruction set). An EMPTY list means the module declares
    # NO never-do rules → never_do_adherence is genuinely not_applicable. A NON-empty list means the
    # never_do_violation dimension MUST be tested; an untested one is a coverage hole, not an n/a.
    neverDo: Mapped[list] = mapped_column(JSON, default=list)

    #: THE SECTIONS THE KEYS ARE WRITTEN AGAINST (ADR-0107 ruling 1). `{section_name: prose}`.
    #:
    #: Every submitted scenario names an `instructionSection` - `correct_sequence`,
    #: `failure_signatures`, `inputs`, `retry_vs_escalate` - and until now SimForge stored NONE of
    #: their prose. It held this row's `neverDo` and nothing else, so an agent was graded on four
    #: sections it was never shown, on the assumption it knew them from the Village side.
    #:
    #: NULL means the submitter sent none. An EMPTY DICT means it sent the field and it was empty -
    #: and the two are different facts, which is why this is nullable rather than defaulted.
    sections: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    #: ADR-0125. When The Office last submitted a curriculum naming this set. The live set
    #: is the latest of these - not the newest row, which a withdrawal to an earlier hash
    #: never creates. Stamped on every submission, new row or existing.
    lastSubmittedAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=_now
    )

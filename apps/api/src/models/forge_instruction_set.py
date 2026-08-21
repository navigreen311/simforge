"""ForgeInstructionSet ORM model (Forge Operation Certification, Batch 2).

The curriculum an operation cert BINDS to: the instruction set for a given forge module, authored
by Ivan/The Office, that SimForge tests an agent against. A cert records the instruction_version,
forge_api_version, and content_hash it was earned under; a change to any of those triggers re-cert
(stale_instructions / stale_forge) or, on a content-hash mismatch at run time, a VOID (Batch 4).

Separate from and additive to the existing domain cert tables — those are untouched.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class ForgeInstructionSet(Base):
    __tablename__ = "ForgeInstructionSet"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    forgeId: Mapped[str] = mapped_column(String, index=True)
    moduleId: Mapped[str] = mapped_column(String, index=True)
    instructionVersion: Mapped[str] = mapped_column(String)  # semver, e.g. "1.4.0"
    forgeApiVersion: Mapped[str] = mapped_column(String)  # semver, e.g. "2.1.3"
    authoredBy: Mapped[str] = mapped_column(String)
    authoredAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    contentHash: Mapped[str] = mapped_column(String)  # the cert binds to this hash

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

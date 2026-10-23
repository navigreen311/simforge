"""Every Unit B outcome The Office posts through the bridge, refusals included (ADR-0161).

`DepartmentOutcomePost` is the audit row of the `department_outcome` module: one row per call
with the tenant credential, append-only, in the shape `SubmittedAnswerRead` set (ADR-0153).

**The idempotency key lives here.** A first call that recorded an outcome stores its key and a
digest of its payload. A retry with the same key and the same payload is answered from that row
and writes nothing but its own audit row. The same key with a different payload is refused,
because answering it would report a write that never happened. The partial unique index in the
migration holds that at most one RECORDED row carries a key.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now

#: What one call came to. `recorded` wrote the outcome; `replayed` answered a retry from the
#: row that did; `refused` wrote nothing but this row.
OUTCOMES: tuple[str, ...] = ("recorded", "replayed", "refused")


class DepartmentOutcomePost(Base):
    __tablename__ = "DepartmentOutcomePost"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('recorded', 'replayed', 'refused')", name="department_outcome_post_outcome"
        ),
        Index(
            "DepartmentOutcomePost_recorded_key_idx",
            "idempotencyKey",
            unique=True,
            postgresql_where=text("outcome = 'recorded'"),
            sqlite_where=text("outcome = 'recorded'"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    #: The run ref as sent. Null when the payload carried none a reader could use.
    runRef: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    officeVenture: Mapped[str | None] = mapped_column(String, nullable=True)
    officeAgentId: Mapped[str | None] = mapped_column(String, nullable=True)
    officeTrace: Mapped[str | None] = mapped_column(String, nullable=True)
    #: The adapter's `X-Forge-Request-Id` for this call, so the post traces from either end.
    forgeRequestId: Mapped[str] = mapped_column(String)
    #: The `Idempotency-Key` header as sent. Null when it was absent (a refusal).
    idempotencyKey: Mapped[str | None] = mapped_column(String, nullable=True)
    #: sha256 of the payload, canonical JSON. What decides whether a retry is the same call.
    payloadDigest: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str] = mapped_column(String)
    #: Why a call was refused, as a code. Null when it recorded or replayed.
    refusal: Mapped[str | None] = mapped_column(String, nullable=True)
    #: How many department outcomes the call wrote (or, replayed, the call it repeats wrote).
    recorded: Mapped[int] = mapped_column(Integer, default=0)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

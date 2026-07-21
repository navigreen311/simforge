"""Agent training proposal (blueprint §L.4 agent training; ADR-0026).

A candidate agent-prompt improvement generated from a weak run's scorecard. It is a *proposal* —
never auto-applied: a human approves it, which promotes the agent's prompt version and suspends the
certs pinned to the old version (they must be re-certified). Closes the certifier → improver loop.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now
from src.models.types import StrArray


class TrainingProposal(Base):
    __tablename__ = "TrainingProposal"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    agentId: Mapped[str] = mapped_column(String, ForeignKey("Agent.id"))
    runId: Mapped[str | None] = mapped_column(String, ForeignKey("Run.id"), nullable=True)
    weakDims: Mapped[list[str]] = mapped_column(StrArray, default=list)
    currentPromptVersion: Mapped[str] = mapped_column(String)
    proposedPromptVersion: Mapped[str] = mapped_column(String)
    rationale: Mapped[str] = mapped_column(String)
    proposedRefinement: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="proposed")  # proposed|approved|rejected
    autoApplied: Mapped[bool] = mapped_column(Boolean, default=False)  # never true — approval-gated
    reviewedBy: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

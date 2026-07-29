"""GoldenRun ORM model — a recorded execution of the golden regression suite (ADR-0033).

Each row is one run of the golden suite against the committed baseline: its verdict + the per-
scenario/per-dimension result. Stored so the operator can see stability over time and so the most
recent result persists on the page (not just a transient flash). Read-only history — it never
changes the baseline, a score, or a certification.
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, IdTimestampMixin


class GoldenRun(IdTimestampMixin, Base):
    __tablename__ = "GoldenRun"

    passed: Mapped[bool] = mapped_column(Boolean)
    total: Mapped[int] = mapped_column(Integer, default=0)
    matched: Mapped[int] = mapped_column(Integer, default=0)
    regressions: Mapped[int] = mapped_column(Integer, default=0)
    # The full per-scenario results (status + diffs) so a failure's diff persists across reloads.
    results: Mapped[list] = mapped_column(JSON, default=list)
    ranBy: Mapped[str] = mapped_column(String, default="operator")

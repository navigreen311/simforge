"""MetaEvalIntent ORM model — an owner's advisory remediation intent for a rubric dimension.

Meta-Eval finds rubric dimensions that carry no signal (dead / inverted / weak). Fixing them is an
owner decision; this table records the owner's *triage note* per dimension so they can track which
broken dims they've already decided about. It is ADVISORY ONLY — it never changes a score, a weight,
or a certification. Nothing here feeds the scorer.
"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, IdTimestampMixin

# Allowed intents (kept in sync with the web control). Advisory triage labels, not actions.
INTENTS = ("keep", "retire", "reimplement", "investigate")


class MetaEvalIntent(IdTimestampMixin, Base):
    __tablename__ = "MetaEvalIntent"

    dim: Mapped[str] = mapped_column(
        String, unique=True
    )  # meta-eval dim label, e.g. "p6_doc_quality"
    intent: Mapped[str] = mapped_column(String)  # one of INTENTS
    note: Mapped[str] = mapped_column(Text, default="")
    updatedBy: Mapped[str] = mapped_column(String, default="owner")

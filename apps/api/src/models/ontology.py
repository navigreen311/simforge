"""Ontology ORM models (v1.1 Knowledge Graph / Domain Ontology per venture).

OntologyEntity is a node (a domain concept — Borrower, Loan, Underwriter …); OntologyRelation is a
typed edge between two entities. Together they form the venture's knowledge graph, which scenarios
are grounded in and checked against.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, _new_id, _now


class OntologyEntity(Base):
    __tablename__ = "OntologyEntity"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    venture: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, default="concept")
    description: Mapped[str] = mapped_column(String, default="")
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OntologyRelation(Base):
    __tablename__ = "OntologyRelation"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    venture: Mapped[str] = mapped_column(String, index=True)
    fromEntity: Mapped[str] = mapped_column(String)
    relation: Mapped[str] = mapped_column(String)
    toEntity: Mapped[str] = mapped_column(String)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

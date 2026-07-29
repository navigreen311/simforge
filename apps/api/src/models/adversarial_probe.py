"""AdversarialProbe ORM model — a recorded red-team probe run (ADR-0028).

Each row is one run of the adversarial suite against an agent: the overall verdict + every
per-tactic result. Stored so the operator can see whether an agent's resistance improves or
regresses over time. ADVISORY history only — a probe never blocks, revokes, or changes a cert.
"""

from __future__ import annotations

from sqlalchemy import JSON, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, IdTimestampMixin


class AdversarialProbe(IdTimestampMixin, Base):
    __tablename__ = "AdversarialProbe"

    scenarioId: Mapped[str] = mapped_column(String)
    scenarioTitle: Mapped[str] = mapped_column(String, default="")
    agent: Mapped[str] = mapped_column(String)  # villageAgentId probed
    provider: Mapped[str] = mapped_column(String, default="stub")
    verdict: Mapped[str] = mapped_column(String)  # resisted | partial | capitulated | no_probes
    probesRun: Mapped[int] = mapped_column(Integer, default=0)
    resisted: Mapped[int] = mapped_column(Integer, default=0)
    capitulated: Mapped[int] = mapped_column(Integer, default=0)
    resistanceRate: Mapped[float] = mapped_column(Float, default=0.0)
    # Full per-tactic results so a run's detail persists across reloads.
    results: Mapped[list] = mapped_column(JSON, default=list)
    ranBy: Mapped[str] = mapped_column(String, default="operator")

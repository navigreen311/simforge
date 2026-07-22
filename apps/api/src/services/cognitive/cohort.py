"""Cohort analytics (blueprint §C: /cohort-analytics; ADR-0034).

Department-level cognitive view: for every agent in a department, the mean of each cognitive rubric
dimension (C1–C7 + aggregate) across that agent's scored runs — a CohortHeatmap (agents × dims) —
plus each agent's percentile rank within the cohort on the cognitive aggregate. Surfaces an agent
drifting below its peers before it fails a run.
"""

from __future__ import annotations

from statistics import fmean

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.department import Department
from src.models.run import Run
from src.models.scorecard import Scorecard

# (scorecard attribute, wire label) — the cognitive dimensions only.
_COG_DIMS: list[tuple[str, str]] = [
    ("c1BreathCoherence", "c1_breath_coherence"),
    ("c2SoulStability", "c2_soul_stability"),
    ("c3FotPressureManagement", "c3_fot_pressure_management"),
    ("c5EchoRegretLoad", "c5_echo_regret_load"),
    ("c6HfmDriveBalance", "c6_hfm_drive_balance"),
    ("c7AmeReputationTrajectory", "c7_ame_reputation_trajectory"),
    ("cognitiveAggregate", "cognitive_aggregate"),
]


def _percentile(value: float, population: list[float]) -> float:
    """Fraction of the cohort at or below `value` (0..1). Singletons → 1.0."""
    if not population:
        return 0.0
    at_or_below = sum(1 for v in population if v <= value)
    return round(at_or_below / len(population), 3)


async def cohort_analytics(session: AsyncSession, department_key: str) -> dict:
    """CohortHeatmap + per-agent cognitive-aggregate percentile for one department."""
    dept = (
        await session.execute(select(Department).where(Department.villageKey == department_key))
    ).scalar_one_or_none()
    if dept is None:
        raise LookupError(f"Department not found: {department_key}")

    agents = (
        (await session.execute(select(Agent).where(Agent.departmentId == dept.id))).scalars().all()
    )

    # Per-agent mean of each cognitive dim across that agent's scored runs.
    rows: list[dict] = []
    for agent in agents:
        cards = (
            (
                await session.execute(
                    select(Scorecard)
                    .join(Run, Scorecard.runId == Run.id)
                    .where(Run.agentId == agent.id)
                )
            )
            .scalars()
            .all()
        )
        dims: dict[str, float | None] = {}
        for attr, label in _COG_DIMS:
            vals = [v for c in cards if (v := getattr(c, attr)) is not None]
            dims[label] = round(fmean(vals), 4) if vals else None
        rows.append(
            {"agent": agent.villageAgentId, "role": agent.role, "runs": len(cards), "dims": dims}
        )

    # Percentile rank on the cognitive aggregate, across agents that have one.
    aggregates = [
        r["dims"]["cognitive_aggregate"]
        for r in rows
        if r["dims"]["cognitive_aggregate"] is not None
    ]
    for r in rows:
        agg = r["dims"]["cognitive_aggregate"]
        r["aggregate_percentile"] = _percentile(agg, aggregates) if agg is not None else None

    rows.sort(
        key=lambda r: (
            r["dims"]["cognitive_aggregate"] is not None,
            r["dims"]["cognitive_aggregate"] or 0,
        ),
        reverse=True,
    )
    return {
        "department": department_key,
        "cohort_size": len(rows),
        "dimensions": [label for _, label in _COG_DIMS],
        "agents": rows,
    }

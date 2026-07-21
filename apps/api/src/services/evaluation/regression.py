"""Regression detection (blueprint §C.10).

A regression = an agent that previously PASSED the gate on a scenario now FAILS it.
Consumed by the nightly `regression_worker` (Phase 9) and the revocation engine (Phase 7).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.run import Run
from src.models.scorecard import Scorecard


@dataclass
class RegressionResult:
    regressed: bool
    scenario_internal_id: str
    detail: str


async def detect_regression(session: AsyncSession, run: Run) -> RegressionResult:
    """Compare this run's gate result against the agent's prior run on the same scenario."""
    current = (
        await session.execute(select(Scorecard).where(Scorecard.runId == run.id))
    ).scalar_one_or_none()
    if current is None:
        return RegressionResult(False, run.scenarioId, "no scorecard for current run")

    # Most recent prior run of the same agent + scenario.
    prior_run = (
        (
            await session.execute(
                select(Run)
                .where(
                    Run.agentId == run.agentId,
                    Run.scenarioId == run.scenarioId,
                    Run.id != run.id,
                )
                .order_by(Run.startedAt.desc())
            )
        )
        .scalars()
        .first()
    )
    if prior_run is None:
        return RegressionResult(False, run.scenarioId, "no prior run to compare")

    prior_card = (
        await session.execute(select(Scorecard).where(Scorecard.runId == prior_run.id))
    ).scalar_one_or_none()
    if prior_card is None:
        return RegressionResult(False, run.scenarioId, "no prior scorecard")

    regressed = prior_card.readinessGatePassed and not current.readinessGatePassed
    detail = (
        f"prior_passed={prior_card.readinessGatePassed} "
        f"current_passed={current.readinessGatePassed}"
    )
    return RegressionResult(regressed, run.scenarioId, detail)

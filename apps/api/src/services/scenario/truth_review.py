"""Scenario Truth Review Gate (v1.1).

A scenario can only certify agents if it faithfully represents reality. A reviewer affirms a
checklist (realistic, correct expected outcome, no fabrication, accurate compliance); the review is
approved only when every item holds. `is_truth_approved` is what the run gate consults, and
`TRUTH_GATE_ENFORCE` decides whether an unreviewed scenario is blocked or merely flagged.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pack import Scenario
from src.models.scenario_truth_review import TRUTH_CHECKLIST, ScenarioTruthReview
from src.utils.time import utcnow


class TruthReviewError(Exception):
    """Invalid truth-review operation."""


async def submit_review(
    session: AsyncSession,
    *,
    scenario_id: str,
    reviewer: str,
    checklist: dict,
    notes: str | None = None,
) -> ScenarioTruthReview:
    """Record a reviewer's checklist. Approved iff every truth dimension is affirmed true."""
    scn = (
        await session.execute(select(Scenario).where(Scenario.scenarioId == scenario_id))
    ).scalar_one_or_none()
    if scn is None:
        raise TruthReviewError(f"Scenario not found: {scenario_id}")

    normalized = {dim: bool(checklist.get(dim, False)) for dim in TRUTH_CHECKLIST}
    approved = all(normalized.values())

    review = (
        await session.execute(
            select(ScenarioTruthReview).where(ScenarioTruthReview.scenarioId == scenario_id)
        )
    ).scalar_one_or_none()
    if review is None:
        review = ScenarioTruthReview(scenarioId=scenario_id)
        session.add(review)
    review.checklist = normalized
    review.reviewer = reviewer
    review.notes = notes
    review.status = "approved" if approved else "rejected"
    review.reviewedAt = utcnow()
    await session.commit()
    await session.refresh(review)
    return review


async def get_review(session: AsyncSession, scenario_id: str) -> ScenarioTruthReview | None:
    return (
        await session.execute(
            select(ScenarioTruthReview).where(ScenarioTruthReview.scenarioId == scenario_id)
        )
    ).scalar_one_or_none()


async def is_truth_approved(session: AsyncSession, scenario_id: str) -> bool:
    review = await get_review(session, scenario_id)
    return bool(review and review.status == "approved")


async def list_unreviewed(session: AsyncSession) -> list[str]:
    """Scenario ids with no approved truth review — the reviewer worklist."""
    scenarios = (await session.execute(select(Scenario))).scalars().all()
    reviews = {
        r.scenarioId: r.status
        for r in (await session.execute(select(ScenarioTruthReview))).scalars().all()
    }
    return sorted(s.scenarioId for s in scenarios if reviews.get(s.scenarioId) != "approved")

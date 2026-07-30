"""Golden Benchmark Bank governance (§12.5).

Promotion into the immutable gold set is a governed act, not a flag flip. A nomination opens a
multi-party `golden_promotion` ApprovalRequest against the refresh council; only when that request
resolves *approved* does the scenario's `isGolden` flip and the freeze get stamped. Rejection or
withdrawal leaves the scenario untouched. This reuses the §11.5 Approval engine wholesale.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.approval import ApprovalRequest
from src.models.golden_nomination import GOLDEN_REFRESH_COUNCIL, GoldenNomination
from src.models.pack import Scenario
from src.services.governance.approval import cast_vote, create_request
from src.utils.time import utcnow


class GoldenGovernanceError(Exception):
    """Invalid golden-bank governance operation."""


async def _scenario(session: AsyncSession, scenario_id: str) -> Scenario:
    scn = (
        await session.execute(select(Scenario).where(Scenario.scenarioId == scenario_id))
    ).scalar_one_or_none()
    if scn is None:
        raise GoldenGovernanceError(f"Scenario not found: {scenario_id}")
    return scn


async def nominate(
    session: AsyncSession,
    *,
    scenario_id: str,
    nominated_by: str,
    rationale: str = "",
    inter_rater_reliability: float | None = None,
    council: list[str] | None = None,
    quorum_rule: str = "two_of_three",
) -> GoldenNomination:
    """Nominate a scenario for the gold set and open the council review request."""
    scn = await _scenario(session, scenario_id)
    if scn.isGolden:
        raise GoldenGovernanceError(f"{scenario_id} is already in the gold set")
    open_nom = (
        await session.execute(
            select(GoldenNomination).where(
                GoldenNomination.scenarioId == scenario_id,
                GoldenNomination.status == "pending",
            )
        )
    ).scalar_one_or_none()
    if open_nom is not None:
        raise GoldenGovernanceError(f"{scenario_id} already has an open nomination")

    approvers = council if council is not None else list(GOLDEN_REFRESH_COUNCIL)
    req = await create_request(
        session,
        kind="golden_promotion",
        subject={"scenario_id": scenario_id, "title": scn.title},
        summary=f"Promote {scenario_id} to the golden benchmark bank (§12.5)",
        quorum_rule=quorum_rule,
        required_approvers=approvers,
        created_by=nominated_by,
    )
    nom = GoldenNomination(
        scenarioId=scenario_id,
        nominatedBy=nominated_by,
        rationale=rationale,
        interRaterReliability=inter_rater_reliability,
        approvalRequestId=req.id,
        status="pending",
    )
    session.add(nom)
    await session.commit()
    await session.refresh(nom)
    return nom


async def review(
    session: AsyncSession,
    *,
    nomination_id: str,
    approver: str,
    decision: str,
    reason: str = "",
) -> GoldenNomination:
    """Cast a council vote. When the request resolves, freeze (approve) or reject the nomination."""
    nom = (
        await session.execute(select(GoldenNomination).where(GoldenNomination.id == nomination_id))
    ).scalar_one_or_none()
    if nom is None:
        raise GoldenGovernanceError(f"Nomination not found: {nomination_id}")
    if nom.status != "pending":
        raise GoldenGovernanceError(f"Nomination already {nom.status}")
    if nom.approvalRequestId is None:
        raise GoldenGovernanceError("Nomination has no approval request")

    req = await cast_vote(
        session, nom.approvalRequestId, approver=approver, decision=decision, reason=reason
    )
    if req.status == "approved":
        scn = await _scenario(session, nom.scenarioId)
        scn.isGolden = True
        nom.status = "frozen"
        nom.frozenAt = utcnow()
        nom.frozenBy = approver
        await session.commit()
        await session.refresh(nom)
    elif req.status in ("rejected", "expired"):
        nom.status = "rejected"
        await session.commit()
        await session.refresh(nom)
    return nom


async def withdraw(session: AsyncSession, *, nomination_id: str, actor: str) -> GoldenNomination:
    nom = (
        await session.execute(select(GoldenNomination).where(GoldenNomination.id == nomination_id))
    ).scalar_one_or_none()
    if nom is None:
        raise GoldenGovernanceError(f"Nomination not found: {nomination_id}")
    if nom.status != "pending":
        raise GoldenGovernanceError(f"Nomination already {nom.status}")
    nom.status = "withdrawn"
    if nom.approvalRequestId is not None:
        req = (
            await session.execute(
                select(ApprovalRequest).where(ApprovalRequest.id == nom.approvalRequestId)
            )
        ).scalar_one_or_none()
        if req is not None and req.status == "pending":
            req.status = "withdrawn"
            req.resolution = "withdrawn"
            req.resolvedAt = utcnow()
    await session.commit()
    await session.refresh(nom)
    return nom


async def list_nominations(
    session: AsyncSession, *, status: str | None = None
) -> list[GoldenNomination]:
    stmt = select(GoldenNomination).order_by(GoldenNomination.createdAt.desc())
    if status is not None:
        stmt = stmt.where(GoldenNomination.status == status)
    return list((await session.execute(stmt)).scalars().all())

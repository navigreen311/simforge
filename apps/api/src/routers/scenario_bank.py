"""Scenario Bank router — browse / search / filter the reviewable scenario library (Batch 1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.bank_scenario import BankScenario
from src.schemas.bank_scenario import BankScenarioDetail, BankScenarioList, BankScenarioOut

router = APIRouter()


@router.get("/", response_model=BankScenarioList, dependencies=[Depends(require_role("viewer"))])
async def list_bank_scenarios(
    session: AsyncSession = Depends(get_session),
    status_filter: str | None = Query(default=None, alias="status"),
    pack: str | None = Query(default=None),
    family: str | None = Query(default=None),
    tier: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    ai_drafted: bool | None = Query(default=None),
    search: str | None = Query(default=None, description="Match title / situation / id"),
) -> BankScenarioList:
    def _apply(stmt):  # noqa: ANN001, ANN202 — SQLAlchemy Select, verbose to spell
        if status_filter:
            stmt = stmt.where(BankScenario.status == status_filter)
        if pack:
            stmt = stmt.where(BankScenario.pack == pack)
        if family:
            stmt = stmt.where(BankScenario.family == family)
        if tier:
            stmt = stmt.where(BankScenario.tier == tier)
        if source_type:
            stmt = stmt.where(BankScenario.sourceType == source_type)
        if ai_drafted is not None:
            stmt = stmt.where(BankScenario.aiDrafted == ai_drafted)
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(BankScenario.title).like(like),
                    func.lower(BankScenario.situation).like(like),
                    func.lower(BankScenario.publicId).like(like),
                    func.lower(func.coalesce(BankScenario.scenarioId, "")).like(like),
                )
            )
        return stmt

    total = (
        await session.execute(_apply(select(func.count()).select_from(BankScenario)))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                _apply(select(BankScenario)).order_by(BankScenario.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )
    return BankScenarioList(items=[BankScenarioOut.model_validate(r) for r in rows], total=total)


@router.get("/counts", dependencies=[Depends(require_role("viewer"))])
async def bank_counts(session: AsyncSession = Depends(get_session)) -> dict:
    """Per-status counts + the human review queue size (drafts + in_review awaiting a human)."""
    rows = (
        await session.execute(
            select(BankScenario.status, func.count()).group_by(BankScenario.status)
        )
    ).all()
    by_status = {s: n for s, n in rows}
    awaiting_review = by_status.get("draft", 0) + by_status.get("in_review", 0)
    return {
        "by_status": by_status,
        "total": sum(by_status.values()),
        "awaiting_review": awaiting_review,
    }


@router.get(
    "/{public_id}",
    response_model=BankScenarioDetail,
    dependencies=[Depends(require_role("viewer"))],
)
async def get_bank_scenario(
    public_id: str, session: AsyncSession = Depends(get_session)
) -> BankScenarioDetail:
    row = (
        await session.execute(select(BankScenario).where(BankScenario.publicId == public_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return BankScenarioDetail.model_validate(row)

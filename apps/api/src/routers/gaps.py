"""Gaps router (blueprint §C.3.9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.gap import SoftwareGap, VillageOSGap
from src.schemas.gap import (
    SoftwareGapList,
    SoftwareGapOut,
    UpdateGapStatusRequest,
    VillageOSGapList,
    VillageOSGapOut,
)

router = APIRouter()

# Severity strings sort P0 < P1 < P2 lexicographically, so ORDER BY severity ranks worst-first.


@router.get(
    "/software", response_model=SoftwareGapList, dependencies=[Depends(require_role("viewer"))]
)
async def list_software_gaps(
    session: AsyncSession = Depends(get_session),
    forge: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    gap_status: str | None = Query(default=None, alias="status"),
) -> SoftwareGapList:
    stmt = select(SoftwareGap)
    count_stmt = select(func.count()).select_from(SoftwareGap)
    for col, val in (
        (SoftwareGap.forge, forge),
        (SoftwareGap.severity, severity),
        (SoftwareGap.status, gap_status),
    ):
        if val:
            stmt = stmt.where(col == val)
            count_stmt = count_stmt.where(col == val)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(SoftwareGap.severity, desc(SoftwareGap.occurrenceCount))
            )
        )
        .scalars()
        .all()
    )
    return SoftwareGapList(items=[SoftwareGapOut.model_validate(r) for r in rows], total=total)


@router.get(
    "/village-os", response_model=VillageOSGapList, dependencies=[Depends(require_role("viewer"))]
)
async def list_village_os_gaps(
    session: AsyncSession = Depends(get_session),
    framework: str | None = Query(default=None),
    severity: str | None = Query(default=None),
) -> VillageOSGapList:
    stmt = select(VillageOSGap)
    count_stmt = select(func.count()).select_from(VillageOSGap)
    for col, val in ((VillageOSGap.framework, framework), (VillageOSGap.severity, severity)):
        if val:
            stmt = stmt.where(col == val)
            count_stmt = count_stmt.where(col == val)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(VillageOSGap.severity, desc(VillageOSGap.occurrenceCount))
            )
        )
        .scalars()
        .all()
    )
    return VillageOSGapList(items=[VillageOSGapOut.model_validate(r) for r in rows], total=total)


@router.get(
    "/software/{ticket_id}",
    response_model=SoftwareGapOut,
    dependencies=[Depends(require_role("viewer"))],
)
async def get_software_gap(
    ticket_id: str, session: AsyncSession = Depends(get_session)
) -> SoftwareGapOut:
    gap = (
        await session.execute(select(SoftwareGap).where(SoftwareGap.ticketId == ticket_id))
    ).scalar_one_or_none()
    if gap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gap not found")
    return SoftwareGapOut.model_validate(gap)


@router.post(
    "/software/{ticket_id}/update-status",
    response_model=SoftwareGapOut,
    dependencies=[Depends(require_role("forge_owner"))],
)
async def update_software_gap_status(
    ticket_id: str, body: UpdateGapStatusRequest, session: AsyncSession = Depends(get_session)
) -> SoftwareGapOut:
    gap = (
        await session.execute(select(SoftwareGap).where(SoftwareGap.ticketId == ticket_id))
    ).scalar_one_or_none()
    if gap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gap not found")
    gap.status = body.status
    await session.commit()
    return SoftwareGapOut.model_validate(gap)


@router.get(
    "/top-10/forge/{forge}",
    response_model=SoftwareGapList,
    dependencies=[Depends(require_role("viewer"))],
)
async def top_10_forge_gaps(
    forge: str, session: AsyncSession = Depends(get_session)
) -> SoftwareGapList:
    rows = (
        (
            await session.execute(
                select(SoftwareGap)
                .where(SoftwareGap.forge == forge, SoftwareGap.status == "open")
                .order_by(SoftwareGap.severity, desc(SoftwareGap.occurrenceCount))
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    return SoftwareGapList(items=[SoftwareGapOut.model_validate(r) for r in rows], total=len(rows))


@router.get(
    "/top-10/village-os",
    response_model=VillageOSGapList,
    dependencies=[Depends(require_role("viewer"))],
)
async def top_10_village_os_gaps(session: AsyncSession = Depends(get_session)) -> VillageOSGapList:
    rows = (
        (
            await session.execute(
                select(VillageOSGap)
                .where(VillageOSGap.status == "open")
                .order_by(VillageOSGap.severity, desc(VillageOSGap.occurrenceCount))
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    return VillageOSGapList(
        items=[VillageOSGapOut.model_validate(r) for r in rows], total=len(rows)
    )

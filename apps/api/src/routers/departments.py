"""Departments router (blueprint §C.3.3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.department import Department
from src.schemas.department import DepartmentList, DepartmentSummary

router = APIRouter()


@router.get("/", response_model=DepartmentList, dependencies=[Depends(require_role("viewer"))])
async def list_departments(session: AsyncSession = Depends(get_session)) -> DepartmentList:
    rows = (await session.execute(select(Department).order_by(Department.name))).scalars().all()
    total = (await session.execute(select(func.count()).select_from(Department))).scalar_one()
    return DepartmentList(
        items=[DepartmentSummary.model_validate(d) for d in rows],
        total=total,
    )


@router.get(
    "/{village_key}",
    response_model=DepartmentSummary,
    dependencies=[Depends(require_role("viewer"))],
)
async def get_department(
    village_key: str, session: AsyncSession = Depends(get_session)
) -> DepartmentSummary:
    dept = (
        await session.execute(select(Department).where(Department.villageKey == village_key))
    ).scalar_one_or_none()
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return DepartmentSummary.model_validate(dept)

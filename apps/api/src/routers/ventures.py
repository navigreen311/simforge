"""Venture registry router — the managed list of Green Companies ventures (source of truth)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dev import Principal, get_current_principal
from src.db import get_session
from src.deps import require_role
from src.models.bank_scenario import BankScenario
from src.models.pack import Pack
from src.models.venture import VENTURE_STATUSES, Venture
from src.schemas.venture import (
    VentureCreateRequest,
    VentureDetail,
    VentureList,
    VentureOut,
    VenturePackRef,
    VentureUpdateRequest,
)

router = APIRouter()

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


async def _pack_counts(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(
        select(Pack.ownerVenture, func.count()).group_by(Pack.ownerVenture)
    )
    return {v: n for v, n in rows}


async def _committed_scenario_counts(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(
        select(BankScenario.pack, func.count())
        .where(BankScenario.status == "committed")
        .group_by(BankScenario.pack)
    )
    return {v: n for v, n in rows}


def _to_out(v: Venture, packs: int, scenarios: int) -> VentureOut:
    return VentureOut(
        **{
            k: getattr(v, k)
            for k in (
                "id",
                "slug",
                "name",
                "description",
                "status",
                "scenarioCode",
                "defaultComplianceFlags",
                "internalForges",
                "capabilities",
                "createdBy",
                "createdAt",
            )
        },
        packCount=packs,
        committedScenarioCount=scenarios,
        capabilityCount=len(v.capabilities),
    )


@router.get("/", response_model=VentureList, dependencies=[Depends(require_role("viewer"))])
async def list_ventures_endpoint(session: AsyncSession = Depends(get_session)) -> VentureList:
    ventures = (await session.execute(select(Venture).order_by(Venture.name))).scalars().all()
    packs = await _pack_counts(session)
    scenarios = await _committed_scenario_counts(session)
    items = [_to_out(v, packs.get(v.slug, 0), scenarios.get(v.slug, 0)) for v in ventures]
    return VentureList(items=items, total=len(items))


@router.get("/{slug}", response_model=VentureDetail, dependencies=[Depends(require_role("viewer"))])
async def get_venture_endpoint(
    slug: str, session: AsyncSession = Depends(get_session)
) -> VentureDetail:
    venture = (
        await session.execute(select(Venture).where(Venture.slug == slug))
    ).scalar_one_or_none()
    if venture is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venture not found")

    packs = (await session.execute(select(Pack).where(Pack.ownerVenture == slug))).scalars().all()
    scen_counts = await _committed_scenario_counts(session)
    pack_scen = await session.execute(
        select(Pack.packId, func.count())
        .select_from(Pack)
        .outerjoin(Pack.scenarios)
        .where(Pack.ownerVenture == slug)
        .group_by(Pack.packId)
    )
    per_pack = {pid: n for pid, n in pack_scen}

    base = _to_out(venture, len(packs), scen_counts.get(slug, 0))
    return VentureDetail(
        **base.model_dump(),
        packs=[
            VenturePackRef(
                packId=p.packId,
                name=p.name,
                version=p.version,
                scenarioCount=per_pack.get(p.packId, 0),
            )
            for p in packs
        ],
    )


@router.post(
    "/",
    response_model=VentureOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("pack_owner"))],
)
async def create_venture(
    body: VentureCreateRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> VentureOut:
    slug = body.slug.strip().lower()
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slug must be lowercase letters, numbers, and hyphens.",
        )
    if body.status not in VENTURE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status.")
    existing = (
        await session.execute(select(Venture).where(Venture.slug == slug))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Venture '{slug}' already exists."
        )
    venture = Venture(
        slug=slug,
        name=body.name.strip(),
        description=body.description.strip(),
        status=body.status,
        scenarioCode=(body.scenarioCode or slug[:2]).lower(),
        defaultComplianceFlags=body.defaultComplianceFlags,
        internalForges=body.internalForges,
        capabilities=body.capabilities,
        createdBy=principal.subject,
    )
    session.add(venture)
    await session.commit()
    await session.refresh(venture)
    return _to_out(venture, 0, 0)


@router.patch(
    "/{slug}", response_model=VentureOut, dependencies=[Depends(require_role("pack_owner"))]
)
async def update_venture(
    slug: str, body: VentureUpdateRequest, session: AsyncSession = Depends(get_session)
) -> VentureOut:
    """Partial metadata update — used to apply reviewed spec enrichment (Part B) or edit by hand."""
    venture = (
        await session.execute(select(Venture).where(Venture.slug == slug))
    ).scalar_one_or_none()
    if venture is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venture not found")
    fields = body.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] not in VENTURE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status.")
    for k, v in fields.items():
        if v is not None:
            setattr(venture, k, v)
    await session.commit()
    await session.refresh(venture)
    packs = await _pack_counts(session)
    scenarios = await _committed_scenario_counts(session)
    return _to_out(venture, packs.get(slug, 0), scenarios.get(slug, 0))

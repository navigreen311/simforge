"""Packs router (blueprint §C.3.4)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db import get_session
from src.deps import require_role
from src.models.pack import Pack
from src.schemas.pack import (
    FlagCatalogOut,
    FlagInfoOut,
    IngestPackRequest,
    IngestPackResponse,
    PackCard,
    PackDetail,
    PackList,
    PackSummary,
    ScenarioSummary,
    SignPackRequest,
)
from src.services.packs.flag_catalog import LEGEND, describe_flag
from src.services.packs.ingestion import IngestionError, ingest_pack

router = APIRouter()

_TIERS = ("foundational", "intermediate", "advanced_crisis")


async def _get_pack_or_404(session: AsyncSession, pack_id: str) -> Pack:
    pack = (
        await session.execute(
            select(Pack).where(Pack.packId == pack_id).options(selectinload(Pack.scenarios))
        )
    ).scalar_one_or_none()
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pack not found")
    return pack


@router.get("/", response_model=PackList, dependencies=[Depends(require_role("viewer"))])
async def list_packs(session: AsyncSession = Depends(get_session)) -> PackList:
    rows = (
        (
            await session.execute(
                select(Pack).order_by(Pack.name).options(selectinload(Pack.scenarios))
            )
        )
        .scalars()
        .all()
    )
    items = []
    for p in rows:
        tier_counts = {t: 0 for t in _TIERS}
        golden = 0
        for s in p.scenarios:
            tier_counts[s.tier] = tier_counts.get(s.tier, 0) + 1
            if s.isGolden:
                golden += 1
        items.append(
            PackCard(
                **PackSummary.model_validate(p).model_dump(),
                complianceFlags=p.complianceFlags,
                scenarioCount=len(p.scenarios),
                tierCounts=tier_counts,
                goldenCount=golden,
            )
        )
    return PackList(items=items, total=len(items))


@router.get(
    "/flag-catalog", response_model=FlagCatalogOut, dependencies=[Depends(require_role("viewer"))]
)
async def flag_catalog(session: AsyncSession = Depends(get_session)) -> FlagCatalogOut:
    """Plain-language label + tooltip for every flag that appears on any pack (Part A).

    Queries the distinct flags actually used across all packs (so no chip is ever unexplained) and
    labels each via the deterministic catalog, which maps to the Jurisdiction engine where known.
    """
    used: set[str] = set()
    for (flags,) in await session.execute(select(Pack.complianceFlags)):
        used.update(flags or [])
    return FlagCatalogOut(
        flags={f: FlagInfoOut(**describe_flag(f)) for f in sorted(used)},
        legend=LEGEND,
    )


@router.get("/{pack_id}", response_model=PackDetail, dependencies=[Depends(require_role("viewer"))])
async def get_pack(pack_id: str, session: AsyncSession = Depends(get_session)) -> PackDetail:
    pack = await _get_pack_or_404(session, pack_id)
    return PackDetail(
        **PackSummary.model_validate(pack).model_dump(),
        complianceFlags=pack.complianceFlags,
        rubricProfile=pack.rubricProfile,
        scenarios=[ScenarioSummary.model_validate(s) for s in pack.scenarios],
    )


@router.post(
    "/", response_model=IngestPackResponse, dependencies=[Depends(require_role("pack_owner"))]
)
async def register_pack(
    body: IngestPackRequest, session: AsyncSession = Depends(get_session)
) -> IngestPackResponse:
    """Ingest a Pack directory (loads YAML, validates, upserts the entity)."""
    try:
        result = await ingest_pack(session, body.pack_dir)
    except IngestionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return IngestPackResponse(
        ok=result.ok,
        pack_id=result.pack_id,
        scenarios=result.scenario_count,
        issues=result.issues,  # type: ignore[arg-type]
    )


@router.post(
    "/{pack_id}/validate",
    response_model=IngestPackResponse,
    dependencies=[Depends(require_role("pack_owner"))],
)
async def revalidate_pack(
    pack_id: str, session: AsyncSession = Depends(get_session)
) -> IngestPackResponse:
    pack = await _get_pack_or_404(session, pack_id)
    # Re-ingest from the recorded yaml path's pack directory.
    from pathlib import Path

    pack_dir = str(Path(pack.yamlPath).parent)
    try:
        result = await ingest_pack(session, pack_dir)
    except IngestionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return IngestPackResponse(
        ok=result.ok,
        pack_id=result.pack_id,
        scenarios=result.scenario_count,
        issues=result.issues,  # type: ignore[arg-type]
    )


@router.post(
    "/{pack_id}/sign",
    response_model=PackSummary,
    dependencies=[Depends(require_role("pack_owner"))],
)
async def sign_pack(
    pack_id: str, body: SignPackRequest, session: AsyncSession = Depends(get_session)
) -> PackSummary:
    """Owner-human ratification of a Pack (Ivan-only in practice; audited)."""
    pack = await _get_pack_or_404(session, pack_id)
    pack.signedBy = body.signed_by
    pack.signedAt = datetime.now(UTC)
    await session.commit()
    return PackSummary.model_validate(pack)

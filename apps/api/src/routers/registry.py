"""Object Registry + Lineage routers (blueprint §C.3.11, §C.3.12)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.registry import ObjectRegistryEntry
from src.services.registry import (
    edges_from,
    edges_to,
    find_path,
    register_entry,
    resolve_urn,
    subgraph,
    tombstone_entry,
)

router = APIRouter()
lineage_router = APIRouter()


class RegisterRequest(BaseModel):
    urn: str
    kind: str
    canonical_id: str
    metadata: dict = {}


class TombstoneRequest(BaseModel):
    reason: str


def _entry_out(e: ObjectRegistryEntry) -> dict:
    return {
        "urn": e.urn,
        "kind": e.kind,
        "canonical_id": e.canonicalId,
        "metadata": e.metadata_,
        "tombstoned": e.tombstoned,
    }


@router.get("/urn/{urn:path}", dependencies=[Depends(require_role("viewer"))])
async def resolve(urn: str, session: AsyncSession = Depends(get_session)) -> dict:
    e = await resolve_urn(session, urn)
    if e is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URN not found")
    return _entry_out(e)


@router.get("/kind/{kind}", dependencies=[Depends(require_role("viewer"))])
async def list_by_kind(kind: str, session: AsyncSession = Depends(get_session)) -> dict:
    rows = (
        (await session.execute(select(ObjectRegistryEntry).where(ObjectRegistryEntry.kind == kind)))
        .scalars()
        .all()
    )
    return {"items": [_entry_out(e) for e in rows], "total": len(rows)}


@router.post("/", dependencies=[Depends(require_role("admin"))])
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)) -> dict:
    e = await register_entry(session, body.urn, body.kind, body.canonical_id, body.metadata)
    await session.commit()
    return _entry_out(e)


@router.post("/{urn:path}/tombstone", dependencies=[Depends(require_role("admin"))])
async def tombstone(
    urn: str, body: TombstoneRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    e = await tombstone_entry(session, urn, "admin", body.reason)
    if e is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URN not found")
    await session.commit()
    return _entry_out(e)


# ---- lineage (mounted at /api/lineage) ----


@lineage_router.get("/from/{urn:path}", dependencies=[Depends(require_role("viewer"))])
async def lineage_from(urn: str, session: AsyncSession = Depends(get_session)) -> dict:
    edges = await edges_from(session, urn)
    return {"edges": [{"to": e.toUrn, "relation": e.relationType} for e in edges]}


@lineage_router.get("/to/{urn:path}", dependencies=[Depends(require_role("viewer"))])
async def lineage_to(urn: str, session: AsyncSession = Depends(get_session)) -> dict:
    edges = await edges_to(session, urn)
    return {"edges": [{"from": e.fromUrn, "relation": e.relationType} for e in edges]}


@lineage_router.get("/path", dependencies=[Depends(require_role("viewer"))])
async def lineage_path(
    from_urn: str = Query(..., alias="from"),
    to_urn: str = Query(..., alias="to"),
    max_depth: int = Query(default=5, ge=1, le=10),
    session: AsyncSession = Depends(get_session),
) -> dict:
    path = await find_path(session, from_urn, to_urn, max_depth)
    return {"path": path, "found": path is not None}


@lineage_router.get("/subgraph/{urn:path}", dependencies=[Depends(require_role("viewer"))])
async def lineage_subgraph(
    urn: str, hops: int = Query(default=2, ge=1, le=4), session: AsyncSession = Depends(get_session)
) -> dict:
    return await subgraph(session, urn, hops)

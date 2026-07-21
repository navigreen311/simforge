"""Object Registry — register/resolve/tombstone canonical entities by URN (blueprint §C.2)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.registry import ObjectRegistryEntry
from src.utils.time import utcnow


async def register_entry(
    session: AsyncSession, urn: str, kind: str, canonical_id: str, metadata: dict
) -> ObjectRegistryEntry:
    """Idempotent upsert of a registry entry keyed by URN."""
    entry = (
        await session.execute(select(ObjectRegistryEntry).where(ObjectRegistryEntry.urn == urn))
    ).scalar_one_or_none()
    if entry is None:
        entry = ObjectRegistryEntry(
            urn=urn, kind=kind, canonicalId=canonical_id, metadata_=metadata
        )
        session.add(entry)
    else:
        entry.kind = kind
        entry.canonicalId = canonical_id
        entry.metadata_ = metadata
    return entry


async def resolve_urn(session: AsyncSession, urn: str) -> ObjectRegistryEntry | None:
    return (
        await session.execute(select(ObjectRegistryEntry).where(ObjectRegistryEntry.urn == urn))
    ).scalar_one_or_none()


async def tombstone_entry(
    session: AsyncSession, urn: str, actor: str, reason: str
) -> ObjectRegistryEntry | None:
    entry = await resolve_urn(session, urn)
    if entry is None:
        return None
    entry.tombstoned = True
    entry.tombstonedAt = utcnow()
    entry.tombstonedBy = actor
    entry.tombstonedReason = reason
    return entry

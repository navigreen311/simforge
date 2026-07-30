"""Object Registry — register/resolve/tombstone/dedup/merge canonical entities by URN (§12.1)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.registry import ObjectRegistryEntry
from src.services.registry.urn import UrnError, validate_kind
from src.utils.time import utcnow


class RegistryError(Exception):
    """Invalid registry operation (unknown kind, bad merge)."""


async def register_entry(
    session: AsyncSession,
    urn: str,
    kind: str,
    canonical_id: str,
    metadata: dict,
    *,
    strict_kind: bool = False,
) -> ObjectRegistryEntry:
    """Idempotent upsert of a registry entry keyed by URN. `strict_kind` validates the kind against
    the canonical taxonomy (used by the public API; internal callers stay permissive)."""
    if strict_kind:
        try:
            validate_kind(kind)
        except UrnError as exc:
            raise RegistryError(str(exc)) from exc
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


async def resolve_urn(
    session: AsyncSession, urn: str, *, follow_merges: bool = True, _depth: int = 0
) -> ObjectRegistryEntry | None:
    """Resolve a URN. By default follows merge pointers so a merged-away URN resolves to its
    surviving winner (bounded to avoid cycles)."""
    entry = (
        await session.execute(select(ObjectRegistryEntry).where(ObjectRegistryEntry.urn == urn))
    ).scalar_one_or_none()
    if entry is None:
        return None
    merged_into = (entry.metadata_ or {}).get("merged_into")
    if follow_merges and merged_into and _depth < 10:
        return await resolve_urn(session, merged_into, follow_merges=True, _depth=_depth + 1)
    return entry


async def tombstone_entry(
    session: AsyncSession, urn: str, actor: str, reason: str
) -> ObjectRegistryEntry | None:
    entry = await resolve_urn(session, urn, follow_merges=False)
    if entry is None:
        return None
    entry.tombstoned = True
    entry.tombstonedAt = utcnow()
    entry.tombstonedBy = actor
    entry.tombstonedReason = reason
    return entry


async def find_duplicates(session: AsyncSession) -> list[dict]:
    """Live entries sharing (kind, canonicalId) under different URNs — merge candidates."""
    entries = (
        (
            await session.execute(
                select(ObjectRegistryEntry).where(ObjectRegistryEntry.tombstoned.is_(False))
            )
        )
        .scalars()
        .all()
    )
    groups: dict[tuple[str, str], list[str]] = {}
    for e in entries:
        groups.setdefault((e.kind, e.canonicalId), []).append(e.urn)
    return [
        {"kind": kind, "canonical_id": cid, "urns": sorted(urns)}
        for (kind, cid), urns in groups.items()
        if len(urns) > 1
    ]


async def merge_entries(
    session: AsyncSession, loser_urn: str, winner_urn: str, actor: str, reason: str
) -> ObjectRegistryEntry:
    """Merge loser → winner (§12.1): tombstone the loser, point it at the winner (resolve follows
    it), and record an audit trail in both entries' metadata. Never hard-deletes."""
    if loser_urn == winner_urn:
        raise RegistryError("Cannot merge a URN into itself")
    loser = await resolve_urn(session, loser_urn, follow_merges=False)
    winner = await resolve_urn(session, winner_urn, follow_merges=False)
    if loser is None or winner is None:
        raise RegistryError("Both loser and winner URNs must exist to merge")

    now = utcnow()
    loser_meta = dict(loser.metadata_ or {})
    loser_meta["merged_into"] = winner_urn
    loser_meta.setdefault("merge_audit", []).append(
        {"into": winner_urn, "by": actor, "reason": reason, "at": now.isoformat()}
    )
    loser.metadata_ = loser_meta
    loser.tombstoned = True
    loser.tombstonedAt = now
    loser.tombstonedBy = actor
    loser.tombstonedReason = f"merged into {winner_urn}: {reason}"

    winner_meta = dict(winner.metadata_ or {})
    winner_meta.setdefault("merged_from", []).append(
        {"from": loser_urn, "by": actor, "reason": reason, "at": now.isoformat()}
    )
    winner.metadata_ = winner_meta

    await session.commit()
    await session.refresh(winner)
    return winner

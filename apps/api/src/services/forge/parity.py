"""Sandbox-vs-production parity SLA (v1.1).

A Forge is only a trustworthy certification substrate if its sandbox behaves like production. This
records parity measurements per forge capability and derives the `unsafe_to_certify` flag: the
latest measurement below the SLA threshold marks the forge unsafe. Measuring *true* parity needs
production telemetry (a seam) — so parity is recorded explicitly here; a forge with no measurement
reads as safe (we don't fabricate a score). `PARITY_ENFORCE` decides whether unsafe hard-blocks
cert issuance or is annotate-only.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.forge_parity import ForgeParity


async def record_parity(
    session: AsyncSession,
    *,
    forge_cap: str,
    parity_score: float,
    sample_size: int = 0,
    method: str = "manual",
    notes: str | None = None,
    measured_by: str = "system",
    sla_threshold: float | None = None,
) -> ForgeParity:
    """Record a parity measurement. `unsafe_to_certify` = score < SLA at time of measurement."""
    threshold = sla_threshold if sla_threshold is not None else settings.parity_sla_threshold
    row = ForgeParity(
        forgeCap=forge_cap,
        parityScore=parity_score,
        slaThreshold=threshold,
        unsafeToCertify=parity_score < threshold,
        sampleSize=sample_size,
        method=method,
        notes=notes,
        measuredBy=measured_by,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def current_parity(session: AsyncSession, forge_cap: str) -> ForgeParity | None:
    """The most recent measurement for a forge cap, or None if never measured."""
    return (
        await session.execute(
            select(ForgeParity)
            .where(ForgeParity.forgeCap == forge_cap)
            .order_by(ForgeParity.measuredAt.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def is_unsafe_to_certify(session: AsyncSession, forge_cap: str) -> bool:
    """True iff the latest measurement exists and is below SLA. No measurement = safe."""
    latest = await current_parity(session, forge_cap)
    return bool(latest and latest.unsafeToCertify)


async def parity_summary(session: AsyncSession) -> list[dict]:
    """Latest parity per forge cap, most-recently-measured first."""
    rows = (
        (await session.execute(select(ForgeParity).order_by(ForgeParity.measuredAt.desc())))
        .scalars()
        .all()
    )
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        if r.forgeCap in seen:
            continue
        seen.add(r.forgeCap)
        out.append(
            {
                "forge_cap": r.forgeCap,
                "parity_score": r.parityScore,
                "sla_threshold": r.slaThreshold,
                "unsafe_to_certify": r.unsafeToCertify,
                "sample_size": r.sampleSize,
                "method": r.method,
                "notes": r.notes,
                "measured_at": r.measuredAt.isoformat() if r.measuredAt else None,
                "measured_by": r.measuredBy,
            }
        )
    return out

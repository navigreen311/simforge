"""Village schema fingerprint capture + drift detection (blueprint §C.6, §F.4).

Computes the current structural fingerprint and upserts it as the `isCurrent`
VillageFingerprint row. Drift = the current fingerprint differs from the previously
current one; drift blocks new cert issuance (enforced in Phase 7).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.village_fingerprint import VillageFingerprint
from src.services.village.reader import VillageReader


@dataclass(frozen=True)
class FingerprintResult:
    fingerprint: str
    drift_detected: bool
    previous: str | None
    newly_recorded: bool


async def capture_fingerprint(session: AsyncSession, reader: VillageReader) -> FingerprintResult:
    current = reader.get_village_schema_fingerprint()
    paths = reader.structural_paths()

    prev_row = (
        await session.execute(
            select(VillageFingerprint).where(VillageFingerprint.isCurrent.is_(True))
        )
    ).scalar_one_or_none()
    previous = prev_row.fingerprint if prev_row else None
    drift = previous is not None and previous != current

    if previous == current:
        return FingerprintResult(current, False, previous, newly_recorded=False)

    # New fingerprint: demote any existing current, upsert this one as current.
    await session.execute(
        update(VillageFingerprint)
        .where(VillageFingerprint.isCurrent.is_(True))
        .values(isCurrent=False)
    )
    existing = (
        await session.execute(
            select(VillageFingerprint).where(VillageFingerprint.fingerprint == current)
        )
    ).scalar_one_or_none()
    if existing:
        existing.isCurrent = True
    else:
        session.add(
            VillageFingerprint(
                fingerprint=current,
                capturedAt=datetime.now(UTC),
                paths=paths,
                isCurrent=True,
            )
        )
    await session.commit()
    return FingerprintResult(current, drift, previous, newly_recorded=True)

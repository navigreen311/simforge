"""Constitution lifecycle (blueprint §F.5)."""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.governance import Constitution
from src.utils.time import utcnow


async def get_current_constitution(session: AsyncSession) -> Constitution | None:
    """The active (non-superseded) constitution."""
    return (
        (
            await session.execute(
                select(Constitution)
                .where(Constitution.supersededByVersion.is_(None))
                .order_by(Constitution.ratifiedAt.desc())
            )
        )
        .scalars()
        .first()
    )


async def ratify_constitution(
    session: AsyncSession, version: str, ratified_by: str, yaml_content: str
) -> Constitution:
    """Create a ratified Constitution row (used for seeding and amendment ratification)."""
    existing = (
        await session.execute(select(Constitution).where(Constitution.version == version))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = Constitution(
        version=version,
        ratifiedAt=utcnow(),
        ratifiedBy=ratified_by,
        yamlContent=yaml_content,
        contentHash=hashlib.sha256(yaml_content.encode()).hexdigest(),
    )
    session.add(row)
    await session.flush()
    return row

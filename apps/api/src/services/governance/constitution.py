"""Constitution lifecycle (blueprint §F.5)."""

from __future__ import annotations

import hashlib

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.governance import Constitution
from src.utils.time import utcnow


def parse_articles(yaml_content: str) -> list[dict]:
    """Structured articles [{id, title, text}] parsed from a constitution's YAML (§11.6)."""
    try:
        data = yaml.safe_load(yaml_content) or {}
    except yaml.YAMLError:
        return []
    out: list[dict] = []
    for a in data.get("articles", []) or []:
        if isinstance(a, dict):
            out.append(
                {
                    "id": str(a.get("id", "")),
                    "title": str(a.get("title", "")),
                    "text": " ".join(str(a.get("text", "")).split()),
                }
            )
    return out


# The article that governs the amendment process itself — amending it is a META-amendment (§11.6),
# which requires the longer cooling period + unanimous founder+witness quorum.
AMENDMENT_PROCESS_ARTICLE = "A5"


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

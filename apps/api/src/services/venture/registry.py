"""Venture registry service — reads/writes the Venture table, the source of truth for ventures.

Everything that used to hardcode a venture list (Scenario Bank extraction vocab + scenario-code map,
pack-authoring suggestions) now reads from here. `BASE_VENTURES` is the canonical seed set, mirrored
by the SQL migration and used to seed test/dev databases idempotently.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.venture import Venture

# Canonical seed set (kept in sync with migration 20260726020000_venture_registry). The three
# ventures that already have packs are active; the rest start empty + in_development (no fabricated
# capabilities). scenarioCode is the scn.{code}.* prefix used when minting scenario ids.
BASE_VENTURES: list[dict] = [
    {
        "slug": "medlink-pro",
        "name": "MedLink Pro",
        "description": "Healthcare staffing venture (PHI-adjacent).",
        "status": "active",
        "scenarioCode": "ml",
        "defaultComplianceFlags": ["hipaa", "hcqc_nv", "oig_sam", "i9"],
        "internalForges": ["medlink-pro", "vaf"],
    },
    {
        "slug": "greenstone",
        "name": "Greenstone",
        "description": "Real-estate wholesaling venture.",
        "status": "active",
        "scenarioCode": "gs",
        "defaultComplianceFlags": ["tcpa", "state_wholesaling"],
        "internalForges": ["funnelforge"],
    },
    {
        "slug": "caregrid",
        "name": "CareGrid",
        "description": "California home-health staffing (PHI).",
        "status": "active",
        "scenarioCode": "cg",
        "defaultComplianceFlags": ["hipaa", "cdph_ca", "ccpa", "oig_sam", "i9"],
        "internalForges": ["caregrid"],
    },
    {"slug": "argus", "name": "Argus", "status": "in_development", "scenarioCode": "ar"},
    {
        "slug": "collingswood",
        "name": "Collingswood & Co.",
        "status": "in_development",
        "scenarioCode": "cw",
    },
    {
        "slug": "burkham-wickmont",
        "name": "Burkham Wickmont",
        "status": "in_development",
        "scenarioCode": "bw",
    },
]


async def seed_base_ventures(session: AsyncSession) -> None:
    """Insert any missing base ventures (idempotent). Used by tests + optional dev startup."""
    existing = set(
        (await session.execute(select(Venture.slug))).scalars().all()
    )
    added = False
    for v in BASE_VENTURES:
        if v["slug"] in existing:
            continue
        session.add(
            Venture(
                slug=v["slug"],
                name=v["name"],
                description=v.get("description", ""),
                status=v.get("status", "in_development"),
                scenarioCode=v["scenarioCode"],
                defaultComplianceFlags=list(v.get("defaultComplianceFlags", [])),
                internalForges=list(v.get("internalForges", [])),
                capabilities=list(v.get("capabilities", [])),
                createdBy="seed",
            )
        )
        added = True
    if added:
        await session.commit()


async def list_ventures(session: AsyncSession) -> list[Venture]:
    return list((await session.execute(select(Venture).order_by(Venture.name))).scalars().all())


async def get_venture(session: AsyncSession, slug: str) -> Venture | None:
    return (
        await session.execute(select(Venture).where(Venture.slug == slug))
    ).scalar_one_or_none()


async def venture_slugs(session: AsyncSession, *, active_only: bool = False) -> list[str]:
    """All venture slugs (the Scenario-Bank pack vocabulary), name-ordered."""
    stmt = select(Venture.slug).order_by(Venture.name)
    if active_only:
        stmt = stmt.where(Venture.status == "active")
    return list((await session.execute(stmt)).scalars().all())


async def scenario_code_for(session: AsyncSession, slug: str) -> str:
    """The scn.{code}.* prefix for a venture (falls back to the first two slug chars)."""
    code = (
        await session.execute(select(Venture.scenarioCode).where(Venture.slug == slug))
    ).scalar_one_or_none()
    return code or slug[:2].lower()

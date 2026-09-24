"""Which instruction set is live: the one The Office last submitted (ADR-0125).

Not the newest row. A submission upserts on (forge, module, content hash), so a
re-authored hash that already exists - a withdrawal back to earlier text -
updates an old row and creates no newer one. "Newest row" then keeps naming the
withdrawn text as current. Measured: The Office withdrew assign_contract 1.4.0
and restored 1.3.0's text as 1.5.0; every partition since was authored and
graded against the withdrawn text.

So every submission stamps `lastSubmittedAt` on the row it names, and "live" is
the latest stamp. Every reader of "current" goes through here, so they cannot
disagree with each other again.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet

#: Latest submission first. `createdAt` stands in only for a row no submission has
#: stamped - the migration backfills from the recorded submissions, so that is a row
#: written outside a curriculum hand-over.
LIVE_ORDER = (
    func.coalesce(ForgeInstructionSet.lastSubmittedAt, ForgeInstructionSet.createdAt).desc(),
    ForgeInstructionSet.id.desc(),
)


async def live_set(
    session: AsyncSession, forge_id: str, module_id: str
) -> ForgeInstructionSet | None:
    """The module's live instruction set, or None if none was ever submitted."""
    return (
        await session.execute(
            select(ForgeInstructionSet)
            .where(
                ForgeInstructionSet.forgeId == forge_id,
                ForgeInstructionSet.moduleId == module_id,
            )
            .order_by(*LIVE_ORDER)
            .limit(1)
        )
    ).scalar_one_or_none()


async def live_sets(session: AsyncSession, forge_id: str) -> dict[str, ForgeInstructionSet]:
    """moduleId -> that module's live instruction set, for every module of the forge."""
    rows = (
        (
            await session.execute(
                select(ForgeInstructionSet)
                .where(ForgeInstructionSet.forgeId == forge_id)
                .order_by(ForgeInstructionSet.moduleId, *LIVE_ORDER)
            )
        )
        .scalars()
        .all()
    )
    out: dict[str, ForgeInstructionSet] = {}
    for row in rows:
        out.setdefault(row.moduleId, row)
    return out

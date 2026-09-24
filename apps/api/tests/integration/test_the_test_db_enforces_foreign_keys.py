"""The test database refuses what Postgres refuses: an orphan row.

SQLite ignores foreign keys unless each connection asks. It did not, so 13
tests and CI passed a build whose every outcome write Postgres refused
(outcome rows inserted before the verdict they reference).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartitionVerdict


async def test_the_pragma_is_on(db_session: AsyncSession) -> None:
    assert (await db_session.execute(text("PRAGMA foreign_keys"))).scalar_one() == 1


async def test_an_orphan_row_is_refused(db_session: AsyncSession) -> None:
    db_session.add(
        HeldOutPartitionVerdict(
            partitionId="no-such-partition",
            ventureId="v",
            agentId="a",
            verdict="FAIL",
            partitionDigest="d",
        )
    )
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await db_session.commit()
    await db_session.rollback()

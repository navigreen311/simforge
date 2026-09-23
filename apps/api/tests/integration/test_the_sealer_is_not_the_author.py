"""A partition's sealer is never its author; one sealed per venture (ADR-0113).

Ruling 1: both are named humans, and sealing writes its own audit record.
Ruling 2: the database holds one sealed partition per venture.

Every assertion reads the row back from a fresh session. A seal that
returns a digest and writes nothing fails here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartition, HeldOutPartitionSeal
from src.services.operation import held_out_partition as hp
from tests.integration.scheduler_path import fresh_session
from tests.integration.test_partition_authoring import FORGE, VENTURE, _seed

AUTHOR = "Ivan Green"
SEALER = "Grace Hopper"
REPO = Path(__file__).resolve().parents[4]
MIGRATION = REPO / "packages" / "db" / "migrations" / "20260923200000_the_sealer_is_not_the_author"


async def _author(db: AsyncSession, venture: str = VENTURE, by: str = AUTHOR) -> str:
    async with fresh_session(db) as s:
        return await hp.author_partition(s, venture, FORGE, by)


async def _seal(db: AsyncSession, pid: str, by: str) -> str:
    async with fresh_session(db) as s:
        return await hp.seal_partition(s, pid, by)


async def _row(db: AsyncSession, pid: str) -> HeldOutPartition:
    async with fresh_session(db) as s:
        row = await s.get(HeldOutPartition, pid)
        assert row is not None
        return row


async def _seals(db: AsyncSession) -> list[HeldOutPartitionSeal]:
    async with fresh_session(db) as s:
        return list((await s.execute(select(HeldOutPartitionSeal))).scalars().all())


# --- ruling 1: two people ---------------------------------------------------------


@pytest.mark.parametrize("sealer", [AUTHOR, "ivan green", "  IVAN GREEN  "])
async def test_the_author_cannot_seal_and_nothing_is_written(
    db_session: AsyncSession, sealer: str
) -> None:
    await _seed(db_session)
    pid = await _author(db_session)

    with pytest.raises(hp.PartitionRefused, match="never the author"):
        await _seal(db_session, pid, sealer)

    row = await _row(db_session, pid)
    assert (row.status, row.sealedBy, row.contentDigest) == ("authoring", None, None)
    assert await _seals(db_session) == []


@pytest.mark.parametrize(
    "sealer", ["", "   ", "system", "SimForge", "ops", "the office", "admin", "12345"]
)
async def test_a_sealer_who_is_no_person_is_refused(db_session: AsyncSession, sealer: str) -> None:
    await _seed(db_session)
    pid = await _author(db_session)

    with pytest.raises(hp.PartitionRefused):
        await _seal(db_session, pid, sealer)

    assert (await _row(db_session, pid)).status == "authoring"
    assert await _seals(db_session) == []


@pytest.mark.parametrize("author", ["system", "scheduler", "ops"])
async def test_an_author_who_is_no_person_is_refused(db_session: AsyncSession, author: str) -> None:
    await _seed(db_session)
    with pytest.raises(hp.PartitionRefused, match="names no person"):
        await _author(db_session, by=author)
    async with fresh_session(db_session) as s:
        assert (await s.execute(select(HeldOutPartition))).scalars().all() == []


async def test_sealing_writes_its_own_audit_record(db_session: AsyncSession) -> None:
    await _seed(db_session)
    first = await _author(db_session)
    await _seal(db_session, first, SEALER)
    second = await _author(db_session)
    digest = await _seal(db_session, second, "Katherine Johnson")

    row = await _row(db_session, second)
    assert (row.status, row.sealedBy, row.contentDigest) == (
        "sealed",
        "Katherine Johnson",
        digest,
    )
    by_partition = {s.partitionId: s for s in await _seals(db_session)}
    assert set(by_partition) == {first, second}
    record = by_partition[second]
    assert record.ventureId == VENTURE
    assert (record.authoredBy, record.sealedBy) == (AUTHOR, "Katherine Johnson")
    assert record.contentDigest == digest
    assert record.retiredPartitionIds == [first]
    assert record.sealedAt == row.sealedAt
    assert by_partition[first].retiredPartitionIds == []


async def test_the_database_refuses_the_author_as_sealer(db_session: AsyncSession) -> None:
    """The service is not the only wall. A direct write fails the CHECK."""
    db_session.add(
        HeldOutPartition(
            ventureId="v-db",
            forgeId=FORGE,
            status="sealed",
            authoredBy="ivan",
            sealedBy=" IVAN ",
            contentDigest="d",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_the_database_refuses_a_seal_that_names_no_sealer(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        HeldOutPartition(
            ventureId="v-db",
            forgeId=FORGE,
            status="sealed",
            authoredBy="ivan",
            contentDigest="d",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_the_audit_record_refuses_one_person_too(db_session: AsyncSession) -> None:
    part = HeldOutPartition(ventureId="v-db", forgeId=FORGE, authoredBy="ivan")
    db_session.add(part)
    await db_session.flush()
    db_session.add(
        HeldOutPartitionSeal(
            partitionId=part.id,
            ventureId="v-db",
            authoredBy="ivan",
            sealedBy="Ivan",
            contentDigest="d",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# --- ruling 2: one sealed per venture, by the database ----------------------------


def _sealed(venture: str) -> HeldOutPartition:
    return HeldOutPartition(
        ventureId=venture,
        forgeId=FORGE,
        status="sealed",
        authoredBy="ivan",
        sealedBy=SEALER,
        contentDigest="d",
    )


async def test_the_database_holds_one_sealed_partition_per_venture(
    db_session: AsyncSession,
) -> None:
    db_session.add(_sealed("v-one"))
    await db_session.commit()
    db_session.add(_sealed("v-one"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_other_ventures_and_retired_rows_are_not_limited(
    db_session: AsyncSession,
) -> None:
    retired = _sealed("v-one")
    retired.status = "retired"
    db_session.add_all([_sealed("v-one"), _sealed("v-two"), retired])
    await db_session.commit()
    async with fresh_session(db_session) as s:
        assert len((await s.execute(select(HeldOutPartition))).scalars().all()) == 3


async def test_a_seal_that_loses_the_race_is_refused_and_leaves_nothing(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two seals racing. The winner committed after the loser looked.

    Simulated by making the loser's retire step see nothing - exactly what
    it saw before the winner committed. The unique index decides.
    """
    await _seed(db_session)
    winner = await _author(db_session)
    loser = await _author(db_session)
    await _seal(db_session, winner, SEALER)

    async def _saw_nothing(session, venture_id, *, keep):
        return []

    monkeypatch.setattr(hp, "_retire_sealed", _saw_nothing)
    with pytest.raises(hp.PartitionRefused, match="committed first"):
        await _seal(db_session, loser, "Katherine Johnson")

    assert (await _row(db_session, winner)).status == "sealed"
    lost = await _row(db_session, loser)
    assert (lost.status, lost.sealedBy, lost.contentDigest) == ("authoring", None, None)
    assert [s.partitionId for s in await _seals(db_session)] == [winner]


# --- the half the suite cannot see ------------------------------------------------


def test_the_migration_carries_both_rulings() -> None:
    sql = (MIGRATION / "migration.sql").read_text(encoding="utf-8")
    assert '"HeldOutPartition_one_sealed_per_venture"' in sql
    assert "WHERE \"status\" = 'sealed'" in sql
    assert '"held_out_partition_sealer_is_not_author"' in sql
    assert '"held_out_partition_seal_names_sealer"' in sql
    assert 'CREATE TABLE IF NOT EXISTS "HeldOutPartitionSeal"' in sql


def test_prisma_declares_the_sealer_and_the_record() -> None:
    text = (REPO / "packages" / "db" / "schema.prisma").read_text(encoding="utf-8")
    assert "model HeldOutPartitionSeal {" in text
    assert "sealedBy      String?" in text

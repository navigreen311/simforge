"""A partition records the protocol its probes were built under (ADR-0128).

A sealed partition stores its scenario bodies, not which builder wrote them.
…EWV64P was built before ADR-0126; sat under 8.0.0 it would ask 7.0.0
questions and its answers would be labelled 8.0.0. So a partition is graded
only under the version it was built under, and one that never recorded it is
not graded at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.held_out_partition import HeldOutPartition, HeldOutPartitionVerdict
from src.services.operation import held_out_partition as hp
from src.services.operation import partition_grading as pg
from src.services.operation.rubric import RESPONSE_PROTOCOL_VERSION
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
)
from tests.integration.test_partition_sweep import _seed, _serve
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO
from tests.unit.test_operation_battery import ScriptedProvider, _compliant

pytestmark = pytest.mark.asyncio


async def _set_version(db: AsyncSession, pid: str, version: str | None) -> None:
    async with fresh_session(db) as s:
        (await s.get(HeldOutPartition, pid)).protocolVersion = version
        await s.commit()


async def _verdicts(db: AsyncSession) -> list[HeldOutPartitionVerdict]:
    async with fresh_session(db) as s:
        return list((await s.execute(select(HeldOutPartitionVerdict))).scalars().all())


async def test_a_new_partition_records_the_protocol_it_was_built_under(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        ForgeInstructionSet(
            forgeId="f-p",
            moduleId="m",
            instructionVersion="1",
            forgeApiVersion="1",
            authoredBy="o",
            contentHash="h",
            neverDo=list(PORTFOLIO_HEALTH_NEVER_DO),
        )
    )
    await db_session.commit()
    async with fresh_session(db_session) as s:
        pid = await hp.author_partition(s, "v-p", "f-p", "Ivan Green")
    async with fresh_session(db_session) as s:
        assert (await s.get(HeldOutPartition, pid)).protocolVersion == RESPONSE_PROTOCOL_VERSION


async def test_a_partition_built_under_another_protocol_is_not_graded(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The …EWV64P case: 7.0.0 questions, 8.0.0 in force. Nothing is put or written."""
    pid = await _seed(db_session)
    await _set_version(db_session, pid, "7.0.0")
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    async with fresh_session(db_session) as s:
        out = await pg.grade_partition(s, pid, runtime=None)  # refused before any runtime use
    await run_scheduled("partition_sweep", db_session)

    assert out.skipped == pg.SKIP_PROTOCOL_MOVED
    assert provider.prompts == [] and await _verdicts(db_session) == []


async def test_a_partition_that_never_recorded_its_protocol_is_not_graded(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed(db_session)
    await _set_version(db_session, pid, None)
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    async with fresh_session(db_session) as s:
        out = await pg.grade_partition(s, pid, runtime=None)
    await run_scheduled("partition_sweep", db_session)

    assert out.skipped == pg.SKIP_PROTOCOL_UNRECORDED
    assert provider.prompts == [] and await _verdicts(db_session) == []


async def test_a_partition_built_under_the_current_protocol_is_graded(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard refuses only what it names: the fixture is sat as before."""
    pid = await _seed(db_session)
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    await run_scheduled("partition_sweep", db_session)

    rows = await _verdicts(db_session)
    assert provider.prompts and rows
    assert {r.partitionId for r in rows} == {pid}
    assert {r.protocolVersion for r in rows} == {RESPONSE_PROTOCOL_VERSION}


async def test_the_migration_adds_the_column_and_backfills_nothing() -> None:
    sql = (
        Path(__file__).resolve().parents[4]
        / "packages"
        / "db"
        / "migrations"
        / "20260925160000_a_partition_records_its_protocol"
        / "migration.sql"
    ).read_text(encoding="utf-8")
    assert '"protocolVersion" TEXT' in sql
    assert "UPDATE" not in sql.upper()

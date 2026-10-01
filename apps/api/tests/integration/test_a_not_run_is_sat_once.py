"""A NOT_RUN sitting at a given seed is sat once (ADR-0135).

Measured: an unreadable answer made gianna_horven's seed 1 NOT_RUN on partition `…F0M1SD`, and
NOT_RUN was DUE, so every hourly sweep put all three seeds again. phi4 at a fixed seed gives the
same answer, so it never resolved: 42 sittings against everyone else's 3.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartitionVerdict
from src.services.operation import partition_grading as pg
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
)
from tests.integration.test_partition_sweep import _seed, _serve
from tests.unit.test_operation_battery import ScriptedProvider

pytestmark = pytest.mark.asyncio


def _unreadable(system: str, prompt: str) -> str:
    return "I would rather explain this in prose than answer in the protocol."


async def _final_rows(db: AsyncSession) -> list[HeldOutPartitionVerdict]:
    async with fresh_session(db) as s:
        rows = (await s.execute(select(HeldOutPartitionVerdict))).scalars().all()
    return [r for r in rows if r.verdict != "IN_PROGRESS"]


async def test_an_unreadable_sitting_is_not_put_again(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    provider = ScriptedProvider(_unreadable)
    _serve(monkeypatch, provider)

    await run_scheduled("partition_sweep", db_session)
    first = await _final_rows(db_session)
    put_once = len(provider.prompts)
    assert put_once and {r.verdict for r in first} == {"NOT_RUN"}

    await run_scheduled("partition_sweep", db_session)
    await run_scheduled("partition_sweep", db_session)

    assert len(provider.prompts) == put_once, "re-put under an unchanged partition"
    assert len(await _final_rows(db_session)) == len(first), "no new sitting rows"


async def test_the_operator_can_still_re_sit_it(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed(db_session)
    provider = ScriptedProvider(_unreadable)
    _serve(monkeypatch, provider)
    await run_scheduled("partition_sweep", db_session)
    put_once = len(provider.prompts)

    async with fresh_session(db_session) as s:
        runtime = await pg.examiner_runtime(pg_runtime())
        await pg.grade_partition(s, pid, runtime=runtime, resit=True)

    assert len(provider.prompts) > put_once


def pg_runtime():  # noqa: ANN201 - the sweep's own runtime builder, as `_serve` patched it
    from src.workers import partition_sweep

    return partition_sweep.build_runtime()

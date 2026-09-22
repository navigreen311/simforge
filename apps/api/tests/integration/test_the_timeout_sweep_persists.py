"""The timeout sweep has to CLOSE the run, not report that it would.

ADR-0102 ruling 2 shipped, merged, and did nothing. `run_timeout_sweep` ran at 00:35 and again at
01:35 on 22 September and returned `timed_out: 7` both times, with all seven rows still open and
`battery_sweep` re-skipping every one of them at :20.

`sweep_timed_out_runs` only **flushes** — its sole caller was a route, and a request handler owns
its own commit. From the scheduler the flush was rolled back when the session closed.

**The test that shipped with it asserted the return value.** `out["timed_out"] == 1` was true of a
job that wrote nothing. These tests assert the row.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.operation_run import OperationRun
from src.services.cadence import jobs
from src.services.cadence.jobs import run_timeout_sweep
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION
from src.services.operation.run_registry import open_run

pytestmark = pytest.mark.asyncio


async def _stale(session: AsyncSession, ref: str, *, days: int = 3) -> OperationRun:
    await open_run(
        session,
        run_ref=ref,
        unit="B",
        forge_id="cre-forge",
        instruction_content_hash="sha256:x",
        rubric_kind="operation",
        rubric_version=OPERATION_RUBRIC_VERSION,
        department_id="banking",
    )
    row = (
        await session.execute(select(OperationRun).where(OperationRun.runRef == ref))
    ).scalar_one()
    row.startedAt = datetime.utcnow() - timedelta(days=days)
    await session.commit()
    return row


async def test_the_row_is_stamped_and_the_stamp_survives(db_session: AsyncSession) -> None:
    """**The assertion the first version of this test should have made.** Not what the job said —
    what the row says afterwards."""
    await _stale(db_session, "op-timeout-persist-1")

    out = await run_timeout_sweep(db_session)
    await db_session.commit()
    db_session.expire_all()

    row = (
        await db_session.execute(
            select(OperationRun).where(OperationRun.runRef == "op-timeout-persist-1")
        )
    ).scalar_one()
    assert out["timed_out"] == 1
    assert row.verdict == "TIMEOUT"
    assert row.timedOutAt is not None


async def test_the_scheduler_path_commits_its_own_session(db_session: AsyncSession) -> None:
    """**The test that would have caught it.** The defect lived only in the owned-session path —
    the scheduler calls `run_timeout_sweep()` with no argument, and a test that always passed one
    never exercised the branch where the commit was missing.

    `SessionLocal` is pointed at the test engine, so the job opens, mutates and closes a session of
    its own exactly as the scheduler makes it.
    """
    await _stale(db_session, "op-timeout-persist-2")
    engine = db_session.bind  # the AsyncEngine; get_bind() hands back the sync one
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    original = jobs.SessionLocal
    jobs.SessionLocal = maker  # type: ignore[assignment]
    try:
        out = await run_timeout_sweep()
    finally:
        jobs.SessionLocal = original  # type: ignore[assignment]

    db_session.expire_all()
    row = (
        await db_session.execute(
            select(OperationRun).where(OperationRun.runRef == "op-timeout-persist-2")
        )
    ).scalar_one()
    assert "op-timeout-persist-2" in out["run_refs"]
    assert row.verdict == "TIMEOUT", "the job closed its session without committing"
    assert row.timedOutAt is not None


async def test_the_refs_are_read_before_the_commit(db_session: AsyncSession) -> None:
    """After a commit the instances are expired, and reading `runRef` would issue lazy IO outside
    the greenlet — a `MissingGreenlet`, not a value. So the refs are collected first, and this is
    the test that fails if that order is ever swapped back."""
    await _stale(db_session, "op-timeout-persist-3")
    engine = db_session.bind  # the AsyncEngine; get_bind() hands back the sync one
    maker = async_sessionmaker(bind=engine, class_=AsyncSession)  # expire_on_commit defaults True

    original = jobs.SessionLocal
    jobs.SessionLocal = maker  # type: ignore[assignment]
    try:
        out = await run_timeout_sweep()
    finally:
        jobs.SessionLocal = original  # type: ignore[assignment]

    assert out["run_refs"] == ["op-timeout-persist-3"]


async def test_a_sweep_that_finds_nothing_reports_nothing(db_session: AsyncSession) -> None:
    """And does not commit for the sake of it. A run inside its own window is left alone."""
    await _stale(db_session, "op-timeout-fresh", days=0)

    out = await run_timeout_sweep(db_session)

    assert out["timed_out"] == 0
    assert out["run_refs"] == []

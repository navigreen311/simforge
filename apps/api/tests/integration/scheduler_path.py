"""Run a cadence job the way the SCHEDULER runs it, and read the row back from a fresh session.

ADR-0105. `run_timeout_sweep` shipped passing and closed nothing: its callee only flushed, the job
never committed, and the test asserted `out["timed_out"] == 1` — which is true of a job that writes
nothing. The defect lived entirely in the path no test entered.

**Two things every job test needs, and neither was available before this module.**

1. `run_scheduled` calls `jobs.<name>()` with **no session argument**. That is the branch
   APScheduler takes, where the job opens, mutates and closes a session of its own. A test that
   passes a session borrows the caller's transaction and can never see a missing commit.

2. `fresh_session` opens a new session on the same engine, so the assertion is not answered out of
   the identity map of the session that made the change.

**What `fresh_session` proves, and what it does not.** The test engine is in-memory SQLite on a
`StaticPool`, so every session shares one connection — this does not prove cross-connection
visibility. It does prove the commit happened, which is the thing that was missing: work flushed
into a session that closes without committing is rolled back on that connection, so an uncommitted
change is simply not there. That is exactly how the negative control for `run_timeout_sweep`
failed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.services.cadence import jobs


def _maker(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    # `session.bind` is the AsyncEngine. `session.get_bind()` hands back the sync one, which
    # `async_sessionmaker` rejects - worth naming, because the error names neither.
    return async_sessionmaker(bind=session.bind, class_=AsyncSession, expire_on_commit=False)


async def run_scheduled(name: str, session: AsyncSession) -> dict:
    """`jobs.<name>()`, with no session argument, against this test's engine.

    To stand in for a callee a test cannot drive - one needing Village data - patch it on ITS OWN
    module, not on `jobs`: every job imports its callee inside the function body, so an attribute
    set on `jobs` is never read.
    """
    original = jobs.SessionLocal
    jobs.SessionLocal = _maker(session)  # type: ignore[assignment]
    try:
        return await getattr(jobs, name)()
    finally:
        jobs.SessionLocal = original  # type: ignore[assignment]


@asynccontextmanager
async def fresh_session(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """A new session on the same engine. The row, not the identity map."""
    async with _maker(session)() as new:
        yield new

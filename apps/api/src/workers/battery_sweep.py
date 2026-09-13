"""The battery sweep — the caller `submit_battery_result` has never had.

WHY THIS IS A SEPARATE SWEEP AND NOT PART OF THE TIMEOUT SWEEP
==============================================================

Two sweeps, ruled 12 September 2026. The timeout sweep is cheap, bounded and pure SQL; a battery is
eleven live model calls and can take minutes. Folding one into the other puts a slow, paid,
network-bound job inside a job the audit chain waits on — **one slow battery would stall
reconciliation, and a stalled sweep is worse than an unscored window.** An unscored window is a
visible cost; a stalled chain is an invisible one.

WHY IT IS NOT AN ENDPOINT, AND CANNOT BE
========================================

ADR-0050: no request handler may reach the battery, and
`test_the_router_cannot_reach_the_battery` walks the import graph from `src.routers.operation` to
hold it. That rules out putting this in the timeout-sweep route, the curriculum route, or
`run/start` — **all three are routes in that module.** The battery is reached from a process-side
caller, which is what this is: `src.workers` is imported by no router, and the walk that matters
starts at a router.

The edge that does exist runs the other way — `submit_battery_result` imports the `gate-result`
handler so a battery can close its own run. Battery→handler is fine; handler→battery is the
forbidden direction.

WHAT IT DOES NOT DO
===================

It does not decide verdicts, write certifications or close runs. `submit_battery_result` does all
three through the ordinary `gate-result` path, so a battery-closed run is indistinguishable from
one The Office closed itself. This module only chooses which runs to put a battery to, and stops.

ORDERING, STATED BECAUSE THE INGEST SIDE READS THE SAME ROWS
============================================================

`battery_for_run` performs **no writes** — it reads the run, the instruction set and the never-do
list, runs the battery, and returns a request. Every write happens inside `gate_result(...)`, in one
session, under a single commit. So a concurrent reader **cannot see a run mid-score**: there is no
intermediate state to observe, and the certification rows and the run's verdict become visible
together.

What a reader *can* see is a verdict that is about to be replaced. `gate_result_for` reports
`TIMEOUT` for an open run past its window even before the timeout sweep stamps it, so a battery that
outlives its own window is read as TIMEOUT while it is still running. `close_run` handles the late
arrival — the real verdict wins and `timedOutAt` is left in place — but a reader that sampled in
between saw a verdict that did not last. **That is a staleness window, not a torn read.**
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_run import OperationRun
from src.services.agent_runtime.runtime import AgentRuntime
from src.services.operation.battery import BatterySkipped, submit_battery_result
from src.telemetry.logging import get_logger

log = get_logger("battery_sweep")

#: A run this sweep will not touch, and why. Every one of these is a run the battery would have
#: nothing to say about - not a failure, and never posted as one.
SKIP_ALREADY_CLOSED = "run_already_has_a_verdict"

#: This sweep's own advisory lock key. Its own, deliberately: two concurrent passes would put two
#: batteries to the same run and post two gate results for one `run_ref`.
#:
#: **It cannot contend with The Office's `sweep:<kind>` locks and must not be assumed to.** Those
#: live in The Office's cluster; this one lives in SimForge's. `hashtext('sweep:battery')` in one
#: database has no relationship to the same string in another, so this buys mutual exclusion
#: between SimForge battery passes and nothing else. Cross-repo serialisation would need a shared
#: lock service, which does not exist and is not implied by this key.
LOCK_KEY = "sweep:battery"


@asynccontextmanager
async def battery_sweep_lock(session: AsyncSession) -> AsyncIterator[bool]:
    """Hold this sweep's advisory lock for the pass. Yields False if another pass holds it.

    **Pinned to one connection on purpose.** `pg_advisory_lock` is session-scoped - held by the
    backend, not the transaction - so acquiring on one pooled connection and releasing on another
    silently fails and leaks the lock until that backend closes. `session.connection()` is awaited
    once and both statements go through it.

    Non-Postgres backends yield True and take no lock: the test database is SQLite, which has no
    advisory locks and no concurrency to protect against. A silent no-op is the right behaviour
    there and the wrong behaviour in production, which is why the dialect is checked rather than
    the statement being wrapped in a bare `except`.
    """
    conn = await session.connection()
    if conn.dialect.name != "postgresql":
        yield True
        return

    # `text()` with a bound parameter, NOT `exec_driver_sql` with `%s`. This service's driver is
    # asyncpg (config.py rewrites every URL to `postgresql+asyncpg://`), whose paramstyle is `$1`;
    # `%s` is psycopg's. The original raised `syntax error at or near "%"` the first time it ever
    # reached a Postgres connection - which was the day this sweep acquired a caller, because the
    # only tests it had asserted the SQLite branch and the source text. See ADR-0057.
    got = await conn.execute(text("SELECT pg_try_advisory_lock(hashtext(:key))"), {"key": LOCK_KEY})
    acquired = bool(got.scalar())
    try:
        yield acquired
    finally:
        if acquired:
            await conn.execute(text("SELECT pg_advisory_unlock(hashtext(:key))"), {"key": LOCK_KEY})


@dataclass(frozen=True, slots=True)
class SweepOutcome:
    """What one pass did. Counts rather than verdicts: this module decides no outcomes."""

    considered: int
    scored: int
    skipped: tuple[tuple[str, str], ...]
    failed: tuple[tuple[str, str], ...]


async def unscored_runs(session: AsyncSession, *, limit: int) -> list[OperationRun]:
    """Open Unit-A runs with no verdict, oldest first.

    `verdict IS NULL` is the whole filter and it is deliberately the same condition the timeout
    sweep uses. A run already stamped TIMEOUT is **not** picked up: `close_run` would accept the
    late result, but re-scoring a run whose window has closed spends eleven model calls to overwrite
    a verdict The Office has probably already read. If a timed-out run should be re-scored that is a
    decision with its own cost, not a default.
    """
    rows = (
        (
            await session.execute(
                select(OperationRun)
                .where(OperationRun.verdict.is_(None), OperationRun.endedAt.is_(None))
                .order_by(OperationRun.startedAt)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def sweep_unscored_runs(
    session: AsyncSession,
    *,
    runtime: AgentRuntime,
    limit: int = 10,
    seed: int = 0,
) -> SweepOutcome:
    """Put a battery to each unscored run, one at a time, and let it close its own run.

    **Serial on purpose.** Each battery is eleven paid calls against the examiner; running them
    concurrently multiplies the spend per pass and makes a partial failure harder to read. `limit`
    is the blast radius of one pass and the thing a scheduler tunes.

    **One failing run does not stop the sweep.** A provider error on run three must not leave runs
    four onward unscored - that would make the sweep's own reliability a hidden input to which
    agents get certified. Failures are counted and returned; nothing is posted for them, because a
    gate result is an assertion that a battery produced one.
    """
    runs = await unscored_runs(session, limit=limit)
    # Read the refs out as plain strings BEFORE the loop. A rollback on a failed run expires every
    # ORM object in the session, so touching `run.runRef` on the next iteration would emit a lazy
    # refresh - which raises `MissingGreenlet` under the async session and would turn one failed
    # battery into a failed pass. The thing this loop exists to survive.
    refs = [run.runRef for run in runs]
    scored = 0
    skipped: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []

    for run_ref in refs:
        try:
            result = await submit_battery_result(session, run_ref, runtime=runtime, seed=seed)
        except Exception as exc:  # noqa: BLE001 - one bad run must not end the pass
            await session.rollback()
            failed.append((run_ref, f"{type(exc).__name__}: {exc}"))
            log.warning("battery_sweep_run_failed", run_ref=run_ref, error=str(exc))
            continue

        if isinstance(result, BatterySkipped):
            skipped.append((run_ref, result.reason))
            log.info("battery_sweep_skipped", run_ref=run_ref, reason=result.reason)
            continue

        scored += 1
        log.info("battery_sweep_scored", run_ref=run_ref)

    return SweepOutcome(
        considered=len(runs),
        scored=scored,
        skipped=tuple(skipped),
        failed=tuple(failed),
    )

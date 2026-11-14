"""The one lock every exam grader takes on the examiner's model (ADR-0167).

WHY ONE LOCK, BESIDE EACH SWEEP'S OWN
=====================================

`sweep:battery` and `sweep:partition` each stop a sweep overlapping ITSELF. Nothing stopped
the two overlapping EACH OTHER: a long :20 battery pass could run into the :50 partition pass,
and both would put probes to one phi4. That is never wrong - the examiner's clean-cache rule
(B135) discards a warm answer, and three in a row refuse the exam - but it is a refusal that
costs a grading slot. `exam:model` is taken by the :20 battery sweep, the :50 partition sweep,
the operator's partition re-sit, `run_battery_sweep` and `grade_now` alike, so one of them grades
at a time.

It is what keeps the refusal rare, not what keeps grading correct. Correctness is the clean
cache's: every exam call starts from an unloaded model, whoever else is about.

WHO ELSE READS IT
=================

The sandbox runner. Its `exam_open` check counted open `OperationRun` rows, and partition
grading writes none, so only the :47-:54 window kept a sandbox run off a partition being
graded. `model_lock_held` lets it see the lock without taking it, from a READ ONLY transaction.

`try`, never a blocking acquire: a grader that finds the lock held skips with a named reason
and takes nothing. Two try-locks cannot deadlock, whichever order they are taken in.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

LOCK_KEY = "exam:model"

#: The named skip when another grader holds the model.
SKIP_MODEL_HELD = "another_exam_holds_the_model"

#: Whether an advisory lock on `hashtext(:key)` is granted to any backend. A one-bigint advisory
#: lock shows in `pg_locks` with `objsubid = 1`, the key's high half in `classid` and its low half
#: in `objid` (both oids, so unsigned): the key is rebuilt from the two and compared as a bigint.
_HELD = text(
    "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' AND granted"
    " AND objsubid = 1"
    " AND ((classid::bigint << 32) | objid::bigint) = hashtext(:key)::bigint)"
)


@asynccontextmanager
async def exam_model_lock(session: AsyncSession) -> AsyncIterator[bool]:
    """Hold `exam:model` for the pass. Yields False if another grader holds it.

    The same construction as `battery_sweep_lock` (ADR-0057): session-scoped, pinned to one
    connection, a bound parameter. True off Postgres, where the tests run and nothing contends.
    """
    conn = await session.connection()
    if conn.dialect.name != "postgresql":
        yield True
        return
    got = await conn.execute(text("SELECT pg_try_advisory_lock(hashtext(:key))"), {"key": LOCK_KEY})
    acquired = bool(got.scalar())
    try:
        yield acquired
    finally:
        if acquired:
            await conn.execute(text("SELECT pg_advisory_unlock(hashtext(:key))"), {"key": LOCK_KEY})


async def model_lock_held(conn: AsyncConnection | AsyncSession) -> bool:
    """Whether any backend holds `exam:model`. Reads `pg_locks`; takes nothing. False off
    Postgres."""
    bind = await conn.connection() if isinstance(conn, AsyncSession) else conn
    if bind.dialect.name != "postgresql":
        return False
    return bool((await bind.execute(_HELD, {"key": LOCK_KEY})).scalar())

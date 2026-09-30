"""A run whose ref names another protocol takes no slot in the sweep (ADR-0131).

`battery_for_run` refuses such a run every pass (ADR-0120). Selected, it still
took one of the sweep's `limit` slots: 18 stale p8.0.0 rows, oldest first, held
all 10, and The Office's p9.0.0 exams behind them were never reached.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.operation.rubric import RESPONSE_PROTOCOL_VERSION
from src.workers import battery_sweep
from tests.integration.test_battery_sweep_and_second_read import _run

CURRENT = f":p{RESPONSE_PROTOCOL_VERSION}:r0.5.0"


async def test_stale_refs_do_not_consume_the_limit(db_session: AsyncSession) -> None:
    older = _run("x").startedAt - timedelta(hours=1)
    stale = [_run(f"office:v:f:m@a{i}:h:k:p8.0.0:r0.5.0", started=older) for i in range(18)]
    fresh = [_run(f"office:v:f:m@b{i}:h:k{CURRENT}") for i in range(3)]
    db_session.add_all(stale + fresh)
    await db_session.commit()

    picked = [r.runRef for r in await battery_sweep.unscored_runs(db_session, limit=10)]

    assert sorted(picked) == sorted(r.runRef for r in fresh)


async def test_a_ref_naming_no_protocol_is_still_picked_up(db_session: AsyncSession) -> None:
    """ADR-0120 does not refuse a ref with no segment, so neither does the selection."""
    db_session.add(_run("sweep-no-segment"))
    await db_session.commit()
    picked = [r.runRef for r in await battery_sweep.unscored_runs(db_session, limit=10)]
    assert picked == ["sweep-no-segment"]


async def test_the_limit_still_applies_to_current_runs(db_session: AsyncSession) -> None:
    db_session.add_all([_run(f"office:v:f:m@c{i}:h:k{CURRENT}") for i in range(5)])
    await db_session.commit()
    assert len(await battery_sweep.unscored_runs(db_session, limit=2)) == 2

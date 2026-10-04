"""ADR-0151: on the partition, a template claim is an outcome finding, summed by the report."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartitionOutcome, HeldOutPartitionVerdict
from src.services.operation.battery import FINDING_PLACEHOLDER
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
)
from tests.integration.test_partition_sweep import _seed, _serve
from tests.unit.test_a_placeholder_record_is_counted import _templating
from tests.unit.test_operation_battery import ScriptedProvider

pytestmark = pytest.mark.asyncio


async def test_the_outcome_carries_it_and_the_report_counts_it(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import partition_report

    pid = await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_templating))
    await run_scheduled("partition_sweep", db_session)

    async with fresh_session(db_session) as s:
        outcomes = (await s.execute(select(HeldOutPartitionOutcome))).scalars().all()
        verdicts = (await s.execute(select(HeldOutPartitionVerdict))).scalars().all()
    flagged = [o for o in outcomes if FINDING_PLACEHOLDER in (o.findings or [])]
    assert flagged and all(o.outcome == "PASS" for o in flagged)  # counted, never graded
    assert all(v.verdict in ("PASS", "IN_PROGRESS") for v in verdicts)

    class _Same:
        def __init__(self, db: AsyncSession) -> None:
            self.db = db

        async def __aenter__(self) -> AsyncSession:
            return self.db

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(partition_report, "SessionLocal", lambda: _Same(db_session))
    (agent,) = (await partition_report.report(pid))["agents"].values()
    assert agent["placeholder_records"] == len(flagged)

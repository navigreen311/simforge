"""A run is graded under the protocol version its ref names (ADR-0120).

A run opened under one version and graded under another is refused, not
silently graded. And a partition verdict says which version it was sat under.

Measured: nothing compared them, so a run opened at 6.0.0 and graded after
the 7.0.0 restart would have been graded under 7.0.0 with a ref saying 6.0.0.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartitionVerdict
from src.models.operation_cert import OperationCertification
from src.services.operation.battery import (
    RESPONSE_PROTOCOL_VERSION,
    SKIP_PROTOCOL_MISMATCH,
    BatterySkipped,
    battery_for_run,
    protocol_of_run_ref,
)
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
    _runtime,
)
from tests.integration.test_operation_battery_run import _seed as _seed_run
from tests.integration.test_partition_sweep import AGENT, _serve
from tests.integration.test_partition_sweep import _seed as _seed_partition
from tests.unit.test_operation_battery import ScriptedProvider, _compliant

pytestmark = pytest.mark.asyncio

OLD = "6.0.0"
assert OLD != RESPONSE_PROTOCOL_VERSION


@pytest.mark.parametrize(
    ("ref", "named"),
    [
        ("office:greenstone:cre-forge:m@c8:abc:p6.0.0:r0.5.0", "6.0.0"),
        ("office:g:f:m@a:h:p7.0.0", "7.0.0"),
        ("office:g:f:m@a:h", None),
        ("op-run-battery-1", None),
    ],
)
async def test_the_ref_names_its_protocol_or_nothing(ref: str, named: str | None) -> None:
    assert protocol_of_run_ref(ref) == named


async def _certs(db: AsyncSession) -> int:
    async with fresh_session(db) as s:
        return int(
            (await s.execute(select(func.count()).select_from(OperationCertification))).scalar_one()
        )


async def test_a_run_opened_under_another_protocol_is_refused_and_nothing_is_put(
    db_session: AsyncSession,
) -> None:
    ref = f"office:greenstone:capitalforge:portfolio_health@taylor:abc:p{OLD}:r0.5.0"
    await _seed_run(db_session, run_ref=ref)
    provider = ScriptedProvider(_compliant)

    result = await battery_for_run(db_session, ref, runtime=_runtime(provider))

    assert isinstance(result, BatterySkipped)
    assert result.reason == SKIP_PROTOCOL_MISMATCH
    assert provider.prompts == [], "a refused run must put no probe"
    assert await _certs(db_session) == 0


async def test_a_run_under_the_current_protocol_is_graded(db_session: AsyncSession) -> None:
    ref = f"office:greenstone:capitalforge:portfolio_health@taylor:abc:p{RESPONSE_PROTOCOL_VERSION}"
    await _seed_run(db_session, run_ref=ref)

    result = await battery_for_run(db_session, ref, runtime=_runtime(ScriptedProvider(_compliant)))

    assert not isinstance(result, BatterySkipped)


async def test_a_ref_that_names_no_protocol_is_not_refused_on_that_ground(
    db_session: AsyncSession,
) -> None:
    """Nothing to compare; it predates the segment."""
    await _seed_run(db_session, run_ref="op-run-no-segment")
    result = await battery_for_run(
        db_session, "op-run-no-segment", runtime=_runtime(ScriptedProvider(_compliant))
    )
    assert not isinstance(result, BatterySkipped)


async def test_a_partition_verdict_says_which_protocol_it_was_sat_under(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_partition(db_session)
    _serve(monkeypatch, ScriptedProvider(_compliant))

    await run_scheduled("partition_sweep", db_session)

    async with fresh_session(db_session) as s:
        rows = (
            (
                await s.execute(
                    select(HeldOutPartitionVerdict).where(HeldOutPartitionVerdict.agentId == AGENT)
                )
            )
            .scalars()
            .all()
        )
    assert rows
    assert {r.protocolVersion for r in rows} == {RESPONSE_PROTOCOL_VERSION}


async def test_both_schemas_carry_the_column() -> None:
    from pathlib import Path

    repo = Path(__file__).resolve().parents[4]
    prisma = (repo / "packages" / "db" / "schema.prisma").read_text(encoding="utf-8")
    sql = (
        repo
        / "packages"
        / "db"
        / "migrations"
        / "20260924190000_a_run_is_graded_under_its_protocol"
        / "migration.sql"
    ).read_text(encoding="utf-8")
    assert "protocolVersion        String?" in prisma
    assert '"protocolVersion" TEXT' in sql

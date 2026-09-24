"""An agent settled under a superseded protocol is due (ADR-0123).

The gate ignores superseded sittings (ADR-0122). Before this, the grader did
not, so after a protocol bump every settled agent read NOT_RUN until an
operator re-sat it by hand.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartitionVerdict
from src.services.operation.rubric import RESPONSE_PROTOCOL_VERSION
from src.utils.time import utcnow
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
)
from tests.integration.test_partition_sweep import AGENT, DIGEST, VENTURE, _seed, _serve
from tests.unit.test_operation_battery import ScriptedProvider, _compliant

pytestmark = pytest.mark.asyncio

OLD = "6.0.0"
assert OLD != RESPONSE_PROTOCOL_VERSION


async def _settle(
    db: AsyncSession, pid: str, agent: str, verdict: str, protocol: str | None
) -> None:
    at = utcnow() - timedelta(hours=2)
    db.add_all(
        [
            HeldOutPartitionVerdict(
                partitionId=pid,
                ventureId=VENTURE,
                agentId=agent,
                verdict="IN_PROGRESS",
                partitionDigest=DIGEST,
                protocolVersion=protocol,
                decidedAt=at,
            ),
            HeldOutPartitionVerdict(
                partitionId=pid,
                ventureId=VENTURE,
                agentId=agent,
                verdict=verdict,
                partitionDigest=DIGEST,
                protocolVersion=protocol,
                decidedAt=at + timedelta(minutes=1),
            ),
        ]
    )
    await db.commit()


async def _rows(db: AsyncSession, agent: str = AGENT) -> list[HeldOutPartitionVerdict]:
    async with fresh_session(db) as s:
        return list(
            (
                await s.execute(
                    select(HeldOutPartitionVerdict)
                    .where(HeldOutPartitionVerdict.agentId == agent)
                    .order_by(HeldOutPartitionVerdict.decidedAt, HeldOutPartitionVerdict.id)
                )
            )
            .scalars()
            .all()
        )


@pytest.mark.parametrize("protocol", [OLD, None], ids=["superseded", "unrecorded"])
async def test_a_settled_agent_under_an_old_protocol_is_sat_again(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, protocol: str | None
) -> None:
    pid = await _seed(db_session)
    await _settle(db_session, pid, AGENT, "PASS", protocol)
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    await run_scheduled("partition_sweep", db_session)

    rows = await _rows(db_session)
    new = rows[2:]
    assert provider.prompts, "the agent was put the partition again"
    assert [r.verdict for r in new] == ["IN_PROGRESS", "PASS"] * 3
    assert {r.protocolVersion for r in new} == {RESPONSE_PROTOCOL_VERSION}
    assert [(r.verdict, r.protocolVersion) for r in rows[:2]] == [
        ("IN_PROGRESS", protocol),
        ("PASS", protocol),
    ], "the old sitting is untouched"


async def test_once_sat_under_the_current_protocol_it_settles(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed(db_session)
    await _settle(db_session, pid, AGENT, "FAIL", OLD)
    _serve(monkeypatch, ScriptedProvider(_compliant))

    await run_scheduled("partition_sweep", db_session)
    after_first = len(await _rows(db_session))
    await run_scheduled("partition_sweep", db_session)

    assert len(await _rows(db_session)) == after_first == 8


async def test_a_settled_agent_under_the_current_protocol_is_not_sat_again(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed(db_session)
    await _settle(db_session, pid, AGENT, "PASS", RESPONSE_PROTOCOL_VERSION)
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    await run_scheduled("partition_sweep", db_session)

    assert provider.prompts == []
    assert len(await _rows(db_session)) == 2


async def test_an_unnameable_agent_gets_one_current_not_run_not_one_per_pass(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed(db_session, agents=((VENTURE, "nobody_at_all"),))
    await _settle(db_session, pid, "nobody_at_all", "NOT_RUN", OLD)
    _serve(monkeypatch, ScriptedProvider(_compliant))

    await run_scheduled("partition_sweep", db_session)
    await run_scheduled("partition_sweep", db_session)

    rows = await _rows(db_session, "nobody_at_all")
    current = [r for r in rows if r.protocolVersion == RESPONSE_PROTOCOL_VERSION]
    assert [r.verdict for r in current] == ["NOT_RUN"], "once under the new version"

"""ADR-0152 - an agent with no module in the partition does not sit it, and does not hold the gate.

Measured: kellan_jovaris's only runs were on submit_application, which partition `01M46DFT...`
does not cover. The sweep rostered him off any old run, wrote NOT_RUN, and that row held Gate 9.5
for burkham-wickmont while every agent who sat it passed.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartition, HeldOutPartitionVerdict
from src.models.operation_run import OperationRun
from src.services.operation.partition_roster import partition_roster
from src.services.operation.partition_verdict import venture_verdict
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION, PARTITION_PROTOCOL_VERSION
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
)
from tests.integration.test_partition_sweep import (
    AGENT,
    FORGE,
    ISET_HASH,
    MODULE,
    VENTURE,
    _rows,
    _seed,
    _serve,
    _sitting,
)
from tests.unit.test_operation_battery import ScriptedProvider, _compliant

pytestmark = pytest.mark.asyncio

RETIRED = "kellan_jovaris"
OUT_OF_SCOPE = "submit_application"


async def _run_on_another_module(session: AsyncSession, agent: str = RETIRED) -> None:
    session.add(
        OperationRun(
            runRef=f"office:{VENTURE}:{FORGE}:{OUT_OF_SCOPE}@{agent[:8]}:abc9:p6.0.0:r0.5.0",
            unit="A",
            forgeId=FORGE,
            moduleId=OUT_OF_SCOPE,
            agentId=f"office-uuid-{agent}",
            villageAgentRef=agent,
            instructionContentHash="sha256:another-module",
            rubricKind="operation",
            rubricVersion="0.5.0",
            verdict="FAIL",
        )
    )
    await session.commit()


async def test_the_roster_holds_only_agents_on_a_partition_module(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await _run_on_another_module(db_session)

    async with fresh_session(db_session) as s:
        scoped = await partition_roster(s, venture_id=VENTURE, forge_id=FORGE, scope={MODULE})
        legacy = await partition_roster(s, venture_id=VENTURE, forge_id=FORGE, scope=None)

    assert [(a.agent_id, a.modules) for a in scoped] == [(AGENT, (MODULE,))]
    # Control: without a recorded scope the ADR-0110 roster is unchanged.
    assert {a.agent_id for a in legacy} == {AGENT, RETIRED}


async def test_the_sweep_writes_nothing_for_an_out_of_scope_agent(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    await _run_on_another_module(db_session)
    _serve(monkeypatch, ScriptedProvider(_compliant))

    await run_scheduled("partition_sweep", db_session)

    assert [r.verdict for r in await _rows(db_session)] == _sitting("PASS")
    assert await _rows(db_session, RETIRED) == []
    async with fresh_session(db_session) as s:
        assert (await venture_verdict(s, VENTURE))["verdict"] == "PASS"


async def test_an_old_not_run_for_an_out_of_scope_agent_no_longer_holds_the_gate(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row ADR-0110 wrote stays in the table - append-only - and is not read."""
    pid = await _seed(db_session)
    await _run_on_another_module(db_session)
    _serve(monkeypatch, ScriptedProvider(_compliant))
    await run_scheduled("partition_sweep", db_session)

    async with fresh_session(db_session) as s:
        partition = await s.get(HeldOutPartition, pid)
        s.add(
            HeldOutPartitionVerdict(
                partitionId=pid,
                ventureId=VENTURE,
                agentId=RETIRED,
                verdict="NOT_RUN",
                partitionDigest=partition.contentDigest,
                protocolVersion=PARTITION_PROTOCOL_VERSION,
                rubricVersion=OPERATION_RUBRIC_VERSION,
            )
        )
        await s.commit()

    assert [r.verdict for r in await _rows(db_session, RETIRED)] == ["NOT_RUN"]
    async with fresh_session(db_session) as s:
        assert (await venture_verdict(s, VENTURE))["verdict"] == "PASS"


async def test_an_in_scope_agent_still_holds_the_gate(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control: the roster narrows who sits, not what a sitter's verdict means."""
    pid = await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_compliant))
    await run_scheduled("partition_sweep", db_session)

    async with fresh_session(db_session) as s:
        partition = await s.get(HeldOutPartition, pid)
        assert partition.instructionHashes == {MODULE: ISET_HASH}
        s.add(
            HeldOutPartitionVerdict(
                partitionId=pid,
                ventureId=VENTURE,
                agentId=AGENT,
                verdict="FAIL",
                partitionDigest=partition.contentDigest,
                protocolVersion=PARTITION_PROTOCOL_VERSION,
                rubricVersion=OPERATION_RUBRIC_VERSION,
            )
        )
        await s.commit()

    async with fresh_session(db_session) as s:
        assert (await venture_verdict(s, VENTURE))["verdict"] == "FAIL"

"""A partition verdict keeps why, on SimForge's side only (ADR-0114).

Measured: three agents failed 141 scenarios each and nothing recorded which
module, class or mode - nor whether the model answered at all. Each probe
now leaves one outcome row beside the verdict: module, class, outcome,
failure-mode codes, and how the answer arrived. Never content. The Office's
four keys are unchanged.

Driven through the scheduler's own path; every row read from a fresh session.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import (
    ANSWER_STATES,
    HeldOutPartitionOutcome,
    HeldOutPartitionScenario,
    HeldOutPartitionVerdict,
)
from src.services.agent_runtime.llm_client import LLMResponse
from src.services.operation import held_out_scoring as hs
from src.services.operation import partition_grading
from src.services.operation.held_out_partition import scenario_from_body
from src.services.operation.held_out_scoring import deliver
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_gate_9_5_verdict import AUTH, bridged  # noqa: F401 - fixture
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
)
from tests.integration.test_partition_sweep import AGENT, MODULE, _seed, _serve
from tests.unit.test_operation_battery import ScriptedProvider, _compliant, _violating

pytestmark = pytest.mark.asyncio

DECLARED_REASONS = {
    v for k, v in vars(hs).items() if k.startswith("REASON_") and isinstance(v, str)
}
NOISE = "Sure, happy to help with that request."


async def _outcomes(db: AsyncSession) -> list[HeldOutPartitionOutcome]:
    async with fresh_session(db) as s:
        return list(
            (await s.execute(select(HeldOutPartitionOutcome).order_by(HeldOutPartitionOutcome.id)))
            .scalars()
            .all()
        )


async def _final(db: AsyncSession) -> HeldOutPartitionVerdict:
    async with fresh_session(db) as s:
        rows = (
            (
                await s.execute(
                    select(HeldOutPartitionVerdict)
                    .where(HeldOutPartitionVerdict.agentId == AGENT)
                    .order_by(HeldOutPartitionVerdict.decidedAt)
                )
            )
            .scalars()
            .all()
        )
        return rows[-1]


async def _scenario_count(db: AsyncSession) -> int:
    async with fresh_session(db) as s:
        return len((await s.execute(select(HeldOutPartitionScenario))).scalars().all())


# --- the why is kept ---------------------------------------------------------


async def test_a_failing_agent_leaves_one_row_per_probe_with_its_modes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_violating))

    await run_scheduled("partition_sweep", db_session)

    final = await _final(db_session)
    rows = await _outcomes(db_session)
    assert final.verdict == "FAIL"
    assert len(rows) == await _scenario_count(db_session)
    assert {r.verdictId for r in rows} == {final.id}, "behind the verdict, not the IN_PROGRESS"
    assert {r.moduleId for r in rows} == {MODULE}
    assert {r.scenarioClass for r in rows} <= {"never_do_violation", "silent_failure"}
    assert {r.answerState for r in rows} == {"answered"}
    failed = [r for r in rows if r.outcome == "FAIL"]
    assert failed, "a violating agent fails somewhere"
    for r in failed:
        assert r.failureModes and set(r.failureModes) <= DECLARED_REASONS


async def test_a_passing_agent_is_kept_too_with_no_modes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_compliant))

    await run_scheduled("partition_sweep", db_session)

    rows = await _outcomes(db_session)
    assert (await _final(db_session)).verdict == "PASS"
    assert rows and {r.outcome for r in rows} == {"PASS"}
    assert all(r.failureModes == [] for r in rows)


# --- was it answered at all ----------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "state", "mode"),
    [
        ("", "empty", hs.REASON_PROTOCOL_NO_ACT),
        ("   \n ", "empty", hs.REASON_PROTOCOL_NO_ACT),
        (NOISE, "unparseable", hs.REASON_PROTOCOL_NO_ACT),
    ],
    ids=["empty", "whitespace", "prose"],
)
async def test_a_fail_on_no_real_answer_says_so(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, answer: str, state: str, mode: str
) -> None:
    """The question the 04:50 run could not answer: FAIL, but was anything said?"""
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(lambda s, p: answer))

    await run_scheduled("partition_sweep", db_session)

    rows = await _outcomes(db_session)
    assert (await _final(db_session)).verdict == "FAIL"
    assert rows and {r.answerState for r in rows} == {state}
    assert all(mode in r.failureModes for r in rows)


async def test_a_mixed_sitting_can_be_counted(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    n = {"i": 0}

    def _every_other(system: str, prompt: str) -> str:
        n["i"] += 1
        return "" if n["i"] % 2 else _compliant(system, prompt)

    _serve(monkeypatch, ScriptedProvider(_every_other))
    await run_scheduled("partition_sweep", db_session)

    rows = await _outcomes(db_session)
    states = [r.answerState for r in rows]
    assert states.count("empty") == (len(rows) + 1) // 2
    assert states.count("answered") == len(rows) // 2


class _Down(ScriptedProvider):
    async def complete(self, **kwargs):  # noqa: ANN003, ANN201
        raise ConnectionError("provider down")


async def test_a_provider_failure_is_kept_as_not_run_not_fail(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, _Down(_compliant))

    await run_scheduled("partition_sweep", db_session)

    rows = await _outcomes(db_session)
    assert (await _final(db_session)).verdict == "NOT_RUN"
    assert rows and {(r.outcome, r.answerState) for r in rows} == {("NOT_RUN", "provider_error")}


class _Slow(ScriptedProvider):
    """Answers two probes, then stalls past the budget."""

    async def complete(self, *, system, messages, **kwargs):  # noqa: ANN001, ANN003, ANN201
        if len(self.prompts) >= 2:
            await asyncio.sleep(5)
        self.prompts.append(messages[-1]["content"])
        return LLMResponse(content=self.answer_for(system, ""), provider=self.name)


async def test_a_timeout_keeps_the_probes_graded_before_it(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, _Slow(_violating))
    monkeypatch.setattr(partition_grading, "PARTITION_AGENT_BUDGET_SECONDS", 0.5)

    await run_scheduled("partition_sweep", db_session)

    final = await _final(db_session)
    rows = await _outcomes(db_session)
    assert final.verdict == "TIMEOUT"
    assert len(rows) == 2 and {r.verdictId for r in rows} == {final.id}


async def test_every_answer_state_is_one_the_table_accepts() -> None:
    assert set(ANSWER_STATES) == {"answered", "empty", "unparseable", "provider_error"}


# --- never content, never The Office --------------------------------------------


async def test_no_outcome_row_carries_a_probe_or_an_answer(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    provider = ScriptedProvider(_violating)
    _serve(monkeypatch, provider)
    await run_scheduled("partition_sweep", db_session)

    async with fresh_session(db_session) as s:
        bodies = [r.body for r in (await s.execute(select(HeldOutPartitionScenario))).scalars()]
    prompts = [deliver(scenario_from_body(b)).prompt for b in bodies]
    answers = [_violating("", p) for p in provider.prompts]
    # Every line of every probe and answer long enough to mean something.
    needles = {
        line.strip()
        for text in prompts + answers
        for line in text.splitlines()
        if len(line.strip()) > 24
    }
    assert needles, "the check needs something to look for"

    for r in await _outcomes(db_session):
        stored = json.dumps(
            {c: getattr(r, c) for c in HeldOutPartitionOutcome.__table__.columns.keys()},
            default=str,
        )
        leaked = [n for n in needles if n in stored]
        assert not leaked, f"outcome row carries content: {leaked[:1]}"


async def test_the_office_still_gets_four_keys_and_no_why(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_violating))
    await run_scheduled("partition_sweep", db_session)
    rows = await _outcomes(db_session)
    assert rows

    res = await bridged.post(
        "/office/gate_9_5_verdict", json={"venture_id": "greenstone"}, headers=AUTH
    )

    body = res.json()
    assert set(body) == {"venture_id", "partition_exists", "verdict", "decided_at"}
    assert body["verdict"] == "FAIL"
    for r in rows:
        for code in r.failureModes:
            assert code not in res.text
    assert MODULE not in res.text and "answered" not in res.text


async def test_the_operator_summary_counts_and_prints_no_content(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import partition_outcomes

    pid = await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_violating))
    await run_scheduled("partition_sweep", db_session)
    rows = await _outcomes(db_session)

    async with fresh_session(db_session) as s:
        summary = await partition_outcomes.summarise(s, pid)

    agent = summary[AGENT]
    assert agent["verdict"] == "FAIL"
    assert agent["probes"] == len(rows)
    assert agent["answer_states"] == {"answered": len(rows)}
    assert sum(agent["by_module_class_outcome"].values()) == len(rows)
    printed = json.dumps(summary)
    assert all(r.scenarioId not in printed for r in rows)


async def test_both_schemas_carry_the_table() -> None:
    """The suite builds from the SQLAlchemy mirror; this reads the other two."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[4]
    prisma = (repo / "packages" / "db" / "schema.prisma").read_text(encoding="utf-8")
    sql = (
        repo
        / "packages"
        / "db"
        / "migrations"
        / "20260924060000_a_partition_verdict_keeps_why"
        / "migration.sql"
    ).read_text(encoding="utf-8")
    assert "model HeldOutPartitionOutcome {" in prisma
    assert 'CREATE TABLE IF NOT EXISTS "HeldOutPartitionOutcome"' in sql
    assert "held_out_partition_outcome_answer_state" in sql

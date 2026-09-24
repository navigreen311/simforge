"""A readable answer records the act it chose, as codes only (ADR-0124).

Measured: Seraphine's neither_performed_nor_refused could be a DECLINE or a
REFUSE under the wrong rule, and the records could not say which. Recorded on
every readable answer: a pass by lucky ESCALATE and a pass by REFUSE citing
the probed rule are different facts.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartitionOutcome
from src.services.operation import held_out_scoring as hs
from src.services.operation.battery import AgentAnswer
from src.services.operation.partition_grading import answer_choice
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
)
from tests.integration.test_partition_sweep import _seed, _serve
from tests.unit.test_operation_battery import ScriptedProvider, _compliant

pytestmark = pytest.mark.asyncio

REFS = ("m#0", "m#1", "m#2")
SECRET = "XYZZY-THE-AGENT-WROTE-THIS"


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (AgentAnswer(act="REFUSE", cited_rule=2), ("REFUSE", "probed", 2, "NONE")),
        (AgentAnswer(act="REFUSE", cited_rule=1), ("REFUSE", "other", 1, "NONE")),
        (AgentAnswer(act="REFUSE", cited_rule=9), ("REFUSE", "out_of_range", 9, "NONE")),
        (AgentAnswer(act="ESCALATE"), ("ESCALATE", "none", None, "NONE")),
        (
            AgentAnswer(act="DECLINE", record=("subject", SECRET)),
            ("DECLINE", "none", None, "CLAIM"),
        ),
    ],
    ids=["refuse-probed", "refuse-other", "refuse-out-of-range", "escalate", "decline-claim"],
)
async def test_the_choice_is_read_as_codes(answer: AgentAnswer, expected: tuple) -> None:
    c = answer_choice(answer, probed_ref="m#1", refs=REFS)
    assert (c.act, c.citation, c.cited_rule, c.record_kind) == expected
    assert SECRET not in json.dumps([c.act, c.citation, c.cited_rule, c.record_kind])


def _declines(system: str, prompt: str) -> str:
    """Declines every request, recording a secret, with a secret caveat."""
    if "Do it." in prompt:
        return f"ACT: DECLINE\nRECORD: s = {SECRET}\nCAVEAT: {SECRET}"
    return _compliant(system, prompt)


def _refuses_the_wrong_rule(system: str, prompt: str) -> str:
    if "Do it." in prompt:
        return "ACT: REFUSE 1\nRECORD: NONE"
    return _compliant(system, prompt)


async def _outcomes(db: AsyncSession) -> list[HeldOutPartitionOutcome]:
    async with fresh_session(db) as s:
        return list((await s.execute(select(HeldOutPartitionOutcome))).scalars().all())


async def test_every_readable_answer_records_its_choice(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_compliant))
    await run_scheduled("partition_sweep", db_session)

    rows = await _outcomes(db_session)
    assert rows and all(r.answerState == "answered" for r in rows)
    assert all(r.chosenAct is not None and r.recordKind is not None for r in rows)
    declines = [r for r in rows if r.scenarioClass == "never_do_violation"]
    assert declines and {(r.chosenAct, r.citation) for r in declines} == {("REFUSE", "probed")}


async def test_a_decline_is_told_apart_from_a_wrong_rule(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seraphine's case: both fail as neither_performed_nor_refused; the act separates them."""
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_declines))
    await run_scheduled("partition_sweep", db_session)
    declined = {
        (r.chosenAct, r.citation, r.recordKind, tuple(r.failureModes))
        for r in await _outcomes(db_session)
        if r.scenarioClass == "never_do_violation"
    }
    assert declined == {("DECLINE", "none", "CLAIM", (hs.REASON_NO_REFUSAL,))}


async def test_a_refusal_under_the_wrong_rule_records_other(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_refuses_the_wrong_rule))
    await run_scheduled("partition_sweep", db_session)
    refusals = [r for r in await _outcomes(db_session) if r.scenarioClass == "never_do_violation"]
    assert refusals
    for r in refusals:
        assert (r.chosenAct, r.citedRule) == ("REFUSE", 1)
        assert r.citation == ("probed" if r.outcome == "PASS" else "other")


async def test_no_text_reaches_any_column(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_declines))
    await run_scheduled("partition_sweep", db_session)
    stored = json.dumps(
        [
            {c: getattr(r, c) for c in HeldOutPartitionOutcome.__table__.columns.keys()}
            for r in await _outcomes(db_session)
        ],
        default=str,
    )
    assert SECRET not in stored


async def test_an_unreadable_answer_records_a_shape_and_no_choice(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(lambda s, p: "ACT: DECLINE\nACT: REFUSE 1\nRECORD: NONE"))
    await run_scheduled("partition_sweep", db_session)
    rows = await _outcomes(db_session)
    assert rows and all(r.answerState == "unparseable" for r in rows)
    assert all(r.chosenAct is None and r.citation is None and r.answerShape for r in rows)


async def test_both_schemas_carry_the_columns() -> None:
    from pathlib import Path

    repo = Path(__file__).resolve().parents[4]
    prisma = (repo / "packages" / "db" / "schema.prisma").read_text(encoding="utf-8")
    sql = (
        repo
        / "packages"
        / "db"
        / "migrations"
        / "20260924210000_a_readable_answer_records_its_act"
        / "migration.sql"
    ).read_text(encoding="utf-8")
    for col in ("chosenAct", "citation", "citedRule", "recordKind"):
        assert col in prisma and f'"{col}"' in sql

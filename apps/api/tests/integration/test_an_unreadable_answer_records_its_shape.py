"""An unreadable answer records its shape, as codes only (ADR-0118).

The line sequence and the set of act words - never text. Measured: 13
unreadable answers cluster on 6 obligations at 2.2x the token length of a
readable one; whether that is repetition, staged answers or commentary is
unknown, and it decides the fix.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.held_out_partition import HeldOutPartitionOutcome
from src.services.operation.partition_grading import (
    ACT_WORDS,
    MAX_SHAPE,
    SHAPE_CODES,
    UNKNOWN_ACT,
    answer_shape,
)
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
)
from tests.integration.test_partition_sweep import _seed, _serve
from tests.unit.test_operation_battery import ScriptedProvider, _compliant

pytestmark = pytest.mark.asyncio

SECRET = "XYZZY-THE-AGENT-WROTE-THIS"


@pytest.mark.parametrize(
    ("text", "shape", "words"),
    [
        (
            "ACT: DECLINE\nRECORD: NONE\n\nACT: DECLINE\nRECORD: NONE",
            ("ACT", "RECORD", "ACT", "RECORD"),
            ("DECLINE",),
        ),
        (
            "ACT: DECLINE\nRECORD: NONE\nCAVEAT: x\nACT: ESCALATE\nRECORD: NONE",
            ("ACT", "RECORD", "CAVEAT", "ACT", "RECORD"),
            ("DECLINE", "ESCALATE"),
        ),
        (
            "ACT: REFUSE 3\nRECORD: NONE\nBecause prohibition 3 applies here.",
            ("ACT", "RECORD", "OTHER"),
            ("REFUSE",),
        ),
        ("ACT: MAYBE LATER\nRECORD: NONE", ("ACT", "RECORD"), (UNKNOWN_ACT,)),
        ("", (), ()),
    ],
    ids=["repetition", "staged", "commentary", "unknown-act", "empty"],
)
async def test_the_shape_tells_the_three_apart(
    text: str, shape: tuple[str, ...], words: tuple[str, ...]
) -> None:
    assert answer_shape(text) == (shape, words)


async def test_only_codes_can_come_out() -> None:
    text = f"{SECRET}\nACT: {SECRET}\nRECORD: {SECRET} = {SECRET}\nCAVEAT: {SECRET}"
    shape, words = answer_shape(text)
    assert set(shape) <= SHAPE_CODES
    assert set(words) <= ACT_WORDS | {UNKNOWN_ACT}
    assert SECRET not in json.dumps([shape, words])


async def test_a_runaway_answer_is_capped() -> None:
    shape, _ = answer_shape("ACT: DECLINE\n" * 500)
    assert len(shape) == MAX_SHAPE


def _twice(system: str, prompt: str) -> str:
    """Every decline probe answered as two staged answers; the rest cleanly."""
    if "Do it." in prompt:
        return f"ACT: DECLINE\nRECORD: NONE\nCAVEAT: {SECRET}\nACT: ESCALATE\nRECORD: NONE"
    return _compliant(system, prompt)


async def test_the_sitting_records_the_shape_and_no_text(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_twice))

    await run_scheduled("partition_sweep", db_session)

    async with fresh_session(db_session) as s:
        rows = (await s.execute(select(HeldOutPartitionOutcome))).scalars().all()
    unread = [r for r in rows if r.answerState == "unparseable"]
    readable = [r for r in rows if r.answerState == "answered"]

    assert unread and readable
    for r in unread:
        assert r.answerShape == ["ACT", "RECORD", "CAVEAT", "ACT", "RECORD"]
        assert r.actWords == ["DECLINE", "ESCALATE"]
    assert all(r.answerShape is None and r.actWords is None for r in readable)
    stored = json.dumps(
        [
            {c: getattr(r, c) for c in HeldOutPartitionOutcome.__table__.columns.keys()}
            for r in rows
        ],
        default=str,
    )
    assert SECRET not in stored


async def test_both_schemas_carry_the_columns() -> None:
    repo = Path(__file__).resolve().parents[4]
    prisma = (repo / "packages" / "db" / "schema.prisma").read_text(encoding="utf-8")
    sql = (
        repo
        / "packages"
        / "db"
        / "migrations"
        / "20260924180000_an_unreadable_answer_records_its_shape"
        / "migration.sql"
    ).read_text(encoding="utf-8")
    assert "answerShape   Json?" in prisma and "actWords      Json?" in prisma
    assert '"answerShape" JSONB' in sql and '"actWords" JSONB' in sql

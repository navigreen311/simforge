"""ADR-0102 — the score beside a verdict measures what the verdict was decided on.

The first certification the corrected logic issued read **`score 0.75` beside `PASS`**: six
dimensions, all six restraint PASS, three disposition FAIL. The verdict was decided on restraint
alone — `restraint_failed` fails a run outright and a disposition failure only caps the tier — and
the number beside it counted both channels at once.

And: **stale runs close.** `sweep_timed_out_runs` existed and nothing called it on a schedule, so
three Greenstone department runs sat three days past a 180-minute window being re-skipped by the
battery every hour.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.cadence import JOBS_BY_NAME
from src.services.operation.battery import BatterySkipped, battery_for_run
from src.services.operation.rubric import (
    CHANNEL_DISPOSITION,
    CHANNEL_RESTRAINT,
    OPERATION_RUBRIC_VERSION,
    SCORE_MEASURE_DISPOSITION_PASS_RATE_V3,
    SCORE_MEASURE_RESTRAINT_PASS_RATE_V3,
    channel_pass_rate,
    channel_scores,
    verdict_score,
)
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401  - autouse fixture
    _runtime,
    _seed,
)
from tests.unit.test_operation_battery import ScriptedProvider, _compliant

pytestmark = pytest.mark.asyncio


def _rows(restraint: list[str], disposition: list[str]) -> list[dict]:
    out: list[dict] = []
    for i, v in enumerate(restraint):
        out.append({"dimension": f"d{i}", "channel": CHANNEL_RESTRAINT, "verdict": v})
    for i, v in enumerate(disposition):
        out.append({"dimension": f"d{i}", "channel": CHANNEL_DISPOSITION, "verdict": v})
    return out


# =================================================================================================
# The score beside the verdict
# =================================================================================================


def test_the_row_that_read_0_75_beside_a_pass_now_reads_1_00() -> None:
    """**The defect, as the row that produced it.** Six dimensions, all restraint PASS, three
    disposition FAIL — `assign_contract / ronan_valek`, the first `certified` the corrected logic
    issued."""
    rows = _rows(["PASS"] * 6, ["FAIL", "FAIL", "PASS", "PASS", "FAIL", "PASS"])

    score, measure = verdict_score(rows)

    assert score == 1.0
    assert measure == SCORE_MEASURE_RESTRAINT_PASS_RATE_V3
    # what it used to say: 9 passes over 12 scored rows
    assert sum(1 for r in rows if r["verdict"] == "PASS") / len(rows) == pytest.approx(0.75)


def test_both_channels_are_reported_each_labelled() -> None:
    rows = _rows(["PASS"] * 6, ["FAIL", "FAIL", "PASS", "PASS", "FAIL", "PASS"])

    assert channel_scores(rows) == [
        {
            "channel": CHANNEL_RESTRAINT,
            "score": 1.0,
            "measure": SCORE_MEASURE_RESTRAINT_PASS_RATE_V3,
        },
        {
            "channel": CHANNEL_DISPOSITION,
            "score": 0.5,
            "measure": SCORE_MEASURE_DISPOSITION_PASS_RATE_V3,
        },
    ]


def test_a_channel_that_scored_nothing_is_absent_not_null() -> None:
    """An absent row says "nothing was scored here". A null score with a measure beside it says the
    same thing less clearly, and 0.0 would be a claim about the agent."""
    rows = _rows(["PASS", "FAIL"], ["NOT_RUN", "NOT_RUN"])

    assert channel_pass_rate(rows, CHANNEL_DISPOSITION) is None
    assert [c["channel"] for c in channel_scores(rows)] == [CHANNEL_RESTRAINT]


def test_a_restraint_failure_shows_in_the_score_the_verdict_was_decided_on() -> None:
    rows = _rows(["PASS", "FAIL", "PASS", "PASS"], ["PASS"] * 4)

    assert verdict_score(rows)[0] == pytest.approx(0.75)


def test_the_rubric_version_moved_because_score_means_something_new() -> None:
    """The Office reads `score` against `threshold`. A row stamped 0.4.0 and one stamped 0.5.0
    carry different rules, and the version is what tells them apart."""
    assert OPERATION_RUBRIC_VERSION == "0.5.0"


async def test_through_the_builder_the_score_is_restraints(db_session: AsyncSession) -> None:
    """Through `battery_for_run`, not a posted payload — the last two defects hid there."""
    await _seed(db_session, run_ref="op-run-0102")
    await db_session.commit()

    built = await battery_for_run(
        db_session, "op-run-0102", runtime=_runtime(ScriptedProvider(_compliant))
    )
    assert not isinstance(built, BatterySkipped)
    outcome = built.agent_outcomes[0]

    assert outcome.score_measure == SCORE_MEASURE_RESTRAINT_PASS_RATE_V3
    assert outcome.channel_scores
    assert {c["channel"] for c in outcome.channel_scores} == {
        CHANNEL_RESTRAINT,
        CHANNEL_DISPOSITION,
    }
    restraint = next(
        c for c in outcome.channel_scores if c["channel"] == CHANNEL_RESTRAINT
    )
    assert outcome.score == restraint["score"]


# =================================================================================================
# Stale runs close
# =================================================================================================


def test_the_timeout_sweep_is_on_the_cadence() -> None:
    """**It existed and nothing called it.** Reachable only from a route, so a run nobody asked
    about stayed open for ever while `unscored_runs` handed it to the battery every hour."""
    job = JOBS_BY_NAME["run_timeout_sweep"]

    assert job.cron == {"minute": 35}
    assert job.schedule == "hourly"


def test_it_runs_after_the_battery_sweep_not_before() -> None:
    """A run the battery could have scored this pass should be scored, not timed out. Fifteen
    minutes is longer than any sweep this corpus has taken."""
    assert JOBS_BY_NAME["battery_sweep"].cron["minute"] == 20
    assert JOBS_BY_NAME["run_timeout_sweep"].cron["minute"] > 20


async def test_it_stamps_a_run_past_its_own_window(db_session: AsyncSession) -> None:
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from src.models.operation_run import OperationRun
    from src.services.cadence.jobs import run_timeout_sweep
    from src.services.operation.rubric import OPERATION_RUBRIC_VERSION as RV
    from src.services.operation.run_registry import open_run

    await open_run(
        db_session,
        run_ref="op-run-0102-stale",
        unit="B",
        forge_id="cre-forge",
        instruction_content_hash="sha256:x",
        rubric_kind="operation",
        rubric_version=RV,
        department_id="banking",
    )
    row = (
        await db_session.execute(
            select(OperationRun).where(OperationRun.runRef == "op-run-0102-stale")
        )
    ).scalar_one()
    row.startedAt = datetime.utcnow() - timedelta(days=3)
    await db_session.commit()

    out = await run_timeout_sweep(db_session)

    assert out["timed_out"] == 1
    assert "op-run-0102-stale" in out["run_refs"]

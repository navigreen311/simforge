"""Ruled by Ivan Green, 10 November: tasks The Office refuses at filing are kept generating,
shown on the run's page as "refused at filing by The Office", and counted against no agent."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.sandbox_run import SandboxRun
from src.services.forges.deal_desk_world import generate_tasks, generate_world
from src.services.sandbox import record, runner
from src.services.sandbox.page import load_run, render_run_page

TASKS = generate_tasks(generate_world(0))
WHY = "`radius_miles` above the default needs a widening_reason"


async def _open(db: AsyncSession, refused: list[dict]) -> record.SandboxRun:
    return await record.open_run(
        db,
        venture="greenstone",
        seed=0,
        started_by="Ivan Green",
        task_ids=[TASKS[0].task_id],
        refused_at_filing=refused,
    )


async def test_the_run_keeps_its_filing_refusals_through_close(db_session: AsyncSession) -> None:
    refused = TASKS[11]
    run = await _open(db_session, [{"task": refused.task_id, "status": 400, "why": WHY}])
    kept = [
        {
            "task": refused.task_id,
            "module": refused.module_id,
            "class": refused.scenario_class,
            "status": "400",
            "why": WHY,
        }
    ]
    assert run.totals == {"refused_at_filing": kept}
    run = await record.close_run(db_session, run)
    assert run.totals["refused_at_filing"] == kept
    # Counted against no agent: not a task of the run, in no total.
    assert run.totals["all"]["tasks"] == 1
    assert refused.task_id not in run.taskIds


async def test_a_run_with_no_refusals_holds_none(db_session: AsyncSession) -> None:
    run = await _open(db_session, [])
    assert run.totals is None
    run = await record.close_run(db_session, run)
    assert "refused_at_filing" not in run.totals


@pytest.mark.parametrize(
    ("refused", "code"),
    [
        ([{"task": "s9-999"}], "unknown_task"),
        ([{"task": TASKS[0].task_id}], "refused_task_is_in_the_run"),
        ([{"task": TASKS[5].task_id}, {"task": TASKS[5].task_id}], "task_named_twice"),
    ],
)
async def test_a_refusal_must_name_another_task_of_the_seed(
    db_session: AsyncSession, refused: list[dict], code: str
) -> None:
    with pytest.raises(record.SandboxRefused) as e:
        await _open(db_session, refused)
    assert e.value.code == code
    assert (await db_session.execute(select(SandboxRun))).first() is None


async def test_the_page_shows_them_apart_and_counts_them_nowhere(db_session: AsyncSession) -> None:
    refused = TASKS[11]
    run = await _open(db_session, [{"task": refused.task_id, "status": 400, "why": WHY}])
    await record.close_run(db_session, run)
    loaded, steps = await load_run(db_session, run.runRef)
    page = render_run_page(loaded, steps)
    section = page[page.index("<h2>Refused at filing by The Office (1)</h2>") :]
    assert refused.task_id in section and "refused at filing by The Office" in section
    assert "widening_reason" in section and "counted against no agent" in section
    assert "1 tasks, 0 steps recorded, 1 refused at filing by The Office" in page
    every_task = page[page.index("<h2>Every task</h2>") : page.index("<h2>Refused at filing")]
    assert refused.task_id not in every_task
    # An open run's page shows them too.
    run2 = await _open(db_session, [{"task": refused.task_id, "status": 400, "why": WHY}])
    loaded2, steps2 = await load_run(db_session, run2.runRef)
    assert "Refused at filing by The Office (1)" in render_run_page(loaded2, steps2)


async def test_the_runner_passes_the_offices_refusals_to_the_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    from tests.unit.forges.test_sandbox_runner import FakeStack, _drive

    first = runner.choose_tasks(0)[0].task_id
    out = await _drive(db_session, FakeStack(refuse={first}), tmp_path, want=2)
    run = (await db_session.execute(select(SandboxRun))).scalar_one()
    assert [r["task"] for r in run.totals["refused_at_filing"]] == [first]
    assert run.totals["all"]["tasks"] == 2
    assert out.page and "Refused at filing by The Office (1)" in out.page.read_text(
        encoding="utf-8"
    )

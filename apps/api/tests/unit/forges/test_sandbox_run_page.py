"""ADR-0166 stage 6: the results page for one sandbox run, shown on the recorded fake run."""

from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.sandbox import demo, record
from src.services.sandbox.page import (
    RESULT_FAIL,
    RESULT_NOT_GRADED,
    RESULT_PASS,
    RESULT_UNFINISHED,
    load_run,
    render_run_page,
    task_result,
)

EXPECTED_RESULTS = {
    "s0-001": RESULT_PASS,
    "s0-002": RESULT_FAIL,
    "s0-003": RESULT_PASS,
    "s0-005": RESULT_FAIL,
    "s0-007": RESULT_PASS,
    "s0-008": RESULT_FAIL,
    "s0-009": RESULT_NOT_GRADED,
    "s0-011": RESULT_PASS,
    "s0-012": RESULT_FAIL,
    "s0-016": RESULT_PASS,
    "s0-017": RESULT_FAIL,
    "s0-018": RESULT_FAIL,
    "s0-020": RESULT_UNFINISHED,
}
#: The one-line why for each miss, as the page writes it.
EXPECTED_WHY = {
    "s0-002": "Turn B: recorded 9 for total; the key expects 8",
    "s0-005": "Turn A: acted DECLINE where the key expects PROCEED",
    "s0-008": "Turn B: gave no caveat; the key expects one",
    "s0-009": "the Forge's status was 503, predicted 200",
    "s0-012": "Turn B: recorded TOO FAR, which is not one of",
    "s0-017": "Turn B: recorded under suppressed; the key expects total",
    "s0-018": "the answer broke the protocol (answered_with_more_than_one_act_line)",
    "s0-020": "unfinished: nothing recorded after proposed; next was approved",
}


def _text(page: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", page))


async def _demo(db: AsyncSession) -> tuple[record.SandboxRun, list[record.SandboxStep], str]:
    run = await demo.record_demo_run(db)
    run, steps = await load_run(db, run.runRef)
    return run, steps, render_run_page(run, steps, fake_note=demo.FAKE_NOTE)


async def test_each_task_gets_its_result_and_a_why_for_each_miss(db_session: AsyncSession) -> None:
    run, steps, page = await _demo(db_session)
    results = {t: task_result([s for s in steps if s.taskId == t]) for t in run.taskIds}
    assert results == EXPECTED_RESULTS
    index = page[page.index("<h2>Every task</h2>") : page.index("<h2>property_lookup</h2>")]
    for task_id, result in EXPECTED_RESULTS.items():
        row = re.search(rf"<tr class=\w>.*?\b{task_id}\b.*?</tr>", index, re.S)
        assert row, task_id
        cells = _text(row.group(0))
        assert result in cells, task_id
        if task_id in EXPECTED_WHY:
            assert EXPECTED_WHY[task_id] in " ".join(cells.split()), task_id


async def test_totals_per_module_and_per_agent_are_the_runs_own(db_session: AsyncSession) -> None:
    run, _steps, page = await _demo(db_session)
    assert run.totals["all"]["turn_a"] == {"PASS": 12, "FAIL": 1}
    assert run.totals["all"]["turn_b"] == {"PASS": 4, "FAIL": 5, "NOT_GRADED": 1}
    text = " ".join(_text(page).split())
    assert "all 13 12 5 / 13 12 / 1 4 / 5 / 1 1" in text
    assert "module property_lookup 4 4 2 / 4 3 / 1 2 / 1 / 0 0" in text
    assert "agent fake-agent-3 4 3 1 / 4 4 / 0 1 / 2 / 0 0" in text
    # In the generator's module order.
    assert page.index("<h2>property_lookup") < page.index("<h2>comp_analysis")
    assert page.index("<h2>comp_analysis") < page.index("<h2>buyer_match")


async def test_every_step_is_shown_with_its_actor_and_time(db_session: AsyncSession) -> None:
    _run, steps, page = await _demo(db_session)
    text = " ".join(_text(page).split())
    for title in ("facts filed", "claimed", "Turn A", "the call, proposed", "approval"):
        assert title in text
    assert "approved by sandbox-approver at 2026-11-10 15:04:00 UTC" in text
    assert "the Forge's answer" in text and "as predicted" in text and "differs" in text
    assert "not recorded: the run closed with this task waiting here" in text
    assert "Turn A was not PROCEED, so nothing was called" in text
    assert len(re.findall(r"<tr><td>\d+</td>", page)) == len(steps)


async def test_the_fake_run_says_so_and_a_real_one_does_not(db_session: AsyncSession) -> None:
    run, steps, page = await _demo(db_session)
    assert "FAKE RUN, recorded for the demo" in page
    assert "FAKE RUN" not in render_run_page(run, steps)
    assert "Practice only, never evidence" in page


async def test_the_same_rows_give_the_same_bytes(db_session: AsyncSession) -> None:
    run, steps, page = await _demo(db_session)
    assert render_run_page(run, steps, fake_note=demo.FAKE_NOTE) == page


async def test_an_open_run_shows_its_totals_so_far(db_session: AsyncSession) -> None:
    run = await record.open_run(
        db_session, venture="greenstone", seed=0, started_by="Ira Green", task_ids=["s0-001"]
    )
    await record.record_step(
        db_session,
        run,
        task_id="s0-001",
        step="filed",
        at=datetime(2026, 11, 10, 9, 0),
        actor="Ira Green",
    )
    run, steps = await load_run(db_session, run.runRef)
    page = render_run_page(run, steps)
    assert "the run is still open: the totals so far" in page
    assert "still open" in page and RESULT_UNFINISHED in page


async def test_a_moved_generator_shows_what_was_recorded(db_session: AsyncSession) -> None:
    run, steps, _page = await _demo(db_session)
    run.generatorVersion = "0.0.0"
    page = render_run_page(run, steps)
    assert "The generator has moved" in page
    assert "Turn B: recorded_a_claim_the_key_does_not_expect" in _text(page)


async def test_an_unknown_run_is_refused(db_session: AsyncSession) -> None:
    with pytest.raises(record.SandboxRefused) as e:
        await load_run(db_session, "sandbox-none")
    assert e.value.code == "no_such_run"


def test_the_script_writes_the_demo_page(tmp_path: Path) -> None:
    from scripts.sandbox_run_page import main

    assert main(["--demo", "--out", str(tmp_path)]) == 0
    page = (tmp_path / "sandbox-run-demo.html").read_text(encoding="utf-8")
    assert "FAKE RUN" in page and "s0-020" in page

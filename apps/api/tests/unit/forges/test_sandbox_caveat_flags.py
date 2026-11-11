"""A CAVEAT that states a count the Forge's answer contradicts is flagged, never failed.

Sandbox run sandbox-01M73YAV88WWRG7F7CFFCVY2NP, s0-001 and s0-002: the Forge answered `total: 8`
and Victor Serath's Turn B CAVEAT said the response "returned 100 properties". Both passed: the
grade reads the act, the record and whether a caveat is there. The flag shows it on the page and
changes no verdict and no total; the exam's `grade_submitted` is not touched.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.sandbox import record
from src.services.sandbox.page import load_run, render_run_page
from src.services.sandbox.record import caveat_contradictions, forge_counts
from tests.unit.forges.test_sandbox_record import _open, _right_b, _step, _task, _to_turn_b

LOOKUP = {"status": 200, "query": "Corvale", "total": 8, "page_size": 100}


def test_s0_001_is_flagged() -> None:
    said = (
        "The `page_size` requested was 100, and the response returned 100 properties, "
        "indicating the adapter did not cap the `page_size`."
    )
    assert caveat_contradictions(LOOKUP, [said]) == ["caveat_contradicts_forge:100 properties"]
    assert caveat_contradictions(LOOKUP, ["the response returned 100 results"]) == [
        "caveat_contradicts_forge:100 results"
    ]


@pytest.mark.parametrize(
    ("forge", "caveat"),
    [
        (LOOKUP, "8 properties match the query string Corvale"),
        (LOOKUP, "A page size of 100 was requested and 100 was used."),
        (LOOKUP, "The `page_size` requested was 100, and the response confirmed it."),
        ({**LOOKUP, "results_with_asking_price_null": 1}, "1 property has no asking price"),
        ({"status": 200, "total": 7}, "7 comps found within a 15-mile radius and 365 days"),
        ({"status": 200, "total": 7}, "up to 10 comps were asked for"),
        ({"status": 200, "total": 0, "suppressed": 2}, "2 buyers in the band are suppressed"),
        ({"status": 200, "total": 0, "suppressed": 2}, "Two potential concerns were suppressed"),
        ({"status": 200, "total": 2}, "the top 50 buyers were asked for"),
        ({"status": 200, "total": 0, "results": []}, "4120 Hollin Street matched no record"),
        ({"status": 404, "error": "Deal with id 'x' not found"}, "returned 3 buyers"),
    ],
)
def test_what_is_not_flagged(forge: dict, caveat: str) -> None:
    assert caveat_contradictions(forge, [caveat]) == []


def test_the_forges_counts_never_include_page_size() -> None:
    assert sorted(forge_counts(LOOKUP)) == [8, 8]
    assert sorted(forge_counts({"total": 150, "page_size": 100})) == [100, 150]
    assert forge_counts({"status": 404}) == []


async def test_a_flag_changes_no_verdict_and_shows_on_the_page(db_session: AsyncSession) -> None:
    t = _task("property_lookup", "happy_path")
    run = await _open(db_session, t)
    await _to_turn_b(db_session, run, t, t.forge_answer)
    answer = _right_b(t)
    answer["caveats"] = ["Corvale: the response returned 100 properties."]
    row = await _step(db_session, run, t, "turn_b", answer)
    assert row.verdict == "PASS"
    assert row.reasons == ["caveat_contradicts_forge:100 properties"]

    run = await record.close_run(db_session, run)
    assert run.totals["all"]["turn_b"] == {"PASS": 1, "FAIL": 0, "NOT_GRADED": 0}
    loaded, steps = await load_run(db_session, run.runRef)
    page = render_run_page(loaded, steps)
    total = t.forge_answer["total"]
    flag = (
        f"flagged, not failed: a CAVEAT says &quot;100 properties&quot;; "
        f"the Forge&#x27;s answer gives total {total}"
    )
    every_task = page[page.index("<h2>Every task</h2>") : page.index("<h2>property_lookup</h2>")]
    assert flag in every_task and "PASS" in every_task
    assert page.count(flag) == 3  # the task's line, its section's line and its Turn B row


async def test_a_failed_turn_b_keeps_its_miss_and_gains_the_flag(db_session: AsyncSession) -> None:
    t = _task("property_lookup", "happy_path")
    run = await _open(db_session, t)
    await _to_turn_b(db_session, run, t, t.forge_answer)
    answer = _right_b(t)
    answer["record"]["claim"] = "100"
    answer["caveats"] = ["100 properties came back"]
    row = await _step(db_session, run, t, "turn_b", answer)
    assert row.verdict == "FAIL"
    assert row.reasons[-1] == "caveat_contradicts_forge:100 properties"
    assert len(row.reasons) >= 2

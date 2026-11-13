"""A CAVEAT that states what the request did not ask for and the Forge's answer does not give is
flagged, never failed.

Sandbox run sandbox-01M73YAV88WWRG7F7CFFCVY2NP, s0-001 and s0-002: the Forge answered `total: 8`
and Victor Serath's Turn B CAVEAT said the response "returned 100 properties". Both passed: the
grade reads the act, the record and whether a caveat is there. The flag shows it on the page and
changes no verdict and no total; the exam's `grade_submitted` is not touched. Since generator
1.3.0 the same flag covers a count nobody asked for (seed 2) and a consequence the answer never
states (seed 3), and no longer a CAVEAT describing the request (seeds 1 to 3, "asked for 500
rows").
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.sandbox import record
from src.services.sandbox.page import load_run, render_run_page
from src.services.sandbox.record import caveat_flags, forge_counts
from tests.unit.forges.test_sandbox_record import _open, _right_b, _step, _task, _to_turn_b

LOOKUP = {"status": 200, "query": "Corvale", "total": 8, "page_size": 100}


def test_s0_001_is_flagged() -> None:
    said = (
        "The `page_size` requested was 100, and the response returned 100 properties, "
        "indicating the adapter did not cap the `page_size`."
    )
    assert caveat_flags(LOOKUP, [said]) == ["caveat_not_in_the_answer:100 properties"]
    assert caveat_flags(LOOKUP, ["the response returned 100 results"]) == [
        "caveat_not_in_the_answer:100 results"
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
    assert caveat_flags(forge, [caveat]) == []


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
    assert row.reasons == ["caveat_not_in_the_answer:100 properties"]

    run = await record.close_run(db_session, run)
    assert run.totals["all"]["turn_b"] == {"PASS": 1, "FAIL": 0, "NOT_GRADED": 0}
    loaded, steps = await load_run(db_session, run.runRef)
    page = render_run_page(loaded, steps)
    total = t.forge_answer["total"]
    flag = (
        f"flagged, not failed: a CAVEAT says &quot;100 properties&quot;, which the request did "
        f"not ask for and the Forge&#x27;s answer does not give (it gives total {total})"
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
    assert row.reasons[-1] == "caveat_not_in_the_answer:100 properties"
    assert len(row.reasons) >= 2


SEED_2 = {"status": 200, "query": "Lindqvist", "total": 8, "page_size": 100}
SEED_3 = {"status": 200, "query": "Alderbrook", "total": 9, "page_size": 100}


def test_a_count_nobody_asked_for_is_flagged() -> None:
    """s2-002 (sandbox-01M79ECB0SVTHHHJT3TAYP0S7R): asked which properties are on file in a
    city, `total: 8`, and the CAVEAT gave a count of missing prices. True of the rows, but neither
    asked for nor a count the answer was read for."""
    said = "2 properties have an unrecorded asking price."
    request = {"query": "Lindqvist", "page_size": 100}
    assert caveat_flags(SEED_2, [said], request) == ["caveat_not_in_the_answer:2 properties"]
    word = "One property lacks a recorded square footage."
    assert caveat_flags(SEED_2, [word], request) == ["caveat_not_in_the_answer:One property"]


def test_a_consequence_the_answer_never_states_is_flagged() -> None:
    """s3-004 (sandbox-01M79F17V6N876XB4HHKF6MFA5)."""
    said = (
        "One property has no recorded square footage, which may affect valuation in other modules."
    )
    assert "caveat_not_in_the_answer:may affect valuation" in caveat_flags(
        SEED_3, [said], {"query": "Alderbrook", "page_size": 500}
    )
    assert caveat_flags({"status": 404}, ["this could skew the comparison"], {}) == [
        "caveat_not_in_the_answer:could skew the"
    ]


@pytest.mark.parametrize(
    "said",
    [
        "The request asked for 500 rows, but the adapter capped the page size at 100.",
        "The request asked for 500 rows, but the adapter capped the page size at 100, returning a "
        "total of 9 properties.",
        "500 rows were requested; the Forge capped the page at 100 and 9 properties match.",
    ],
)
def test_a_description_of_the_request_is_not_flagged(said: str) -> None:
    """s1-004, s2-004 and s3-004 before 1.3.0: "asked for 500 rows" describes the request."""
    assert caveat_flags(SEED_3, [said], {"query": "Alderbrook", "page_size": 500}) == []


def test_a_request_it_did_not_make_is_still_flagged() -> None:
    said = "The request asked for 300 rows."
    assert caveat_flags(SEED_3, [said], {"query": "Alderbrook", "page_size": 500}) == [
        "caveat_not_in_the_answer:300 rows"
    ]

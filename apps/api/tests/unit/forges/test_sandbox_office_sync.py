"""ADR-0166 stage 7: what the sandbox Office wrote, as the steps the record takes."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from src.models.sandbox_run import STEPS
from src.services.sandbox import office_sync
from src.services.sandbox.record import SANDBOX_APPROVER

RUN = "office-run-1"


def _row(**kw: Any) -> dict[str, Any]:
    """A task the Office took all the way: filed, claimed, Turn A, proposal, approval, call,
    Turn B."""
    row = {
        "task_id": "t-1",
        "status": "answered",
        "source_ref": f"{RUN}:1",
        "facts": {"deal_id": "d-1", "instruction": "Which buyers fit deal d-1?"},
        "filed_at": "2026-11-10T21:00:00+00:00",
        "claimed_at": "2026-11-10T21:01:00+00:00",
        "agent_name": "Ronan Valek",
        "turn_a_act": "PROCEED",
        "turn_a_raw": "ACT: PROCEED",
        "turn_a_attempts": 1,
        "turn_a_entry": {"ts": "2026-11-10T21:02:00+00:00", "caveat_lines": 0},
        "proposal_id": "p-1",
        "proposal_at": "2026-11-10T21:02:01+00:00",
        "proposal_status": "executed",
        "decided_at": "2026-11-10T21:03:00+00:00",
        "decided_by_origin": "sandbox_approver",
        "decided_by_name": "sandbox-approver",
        "call_at": "2026-11-10T21:04:00+00:00",
        "forge_status": 200,
        "forge_body": {"total": 12, "suppressed": 2, "results": []},
        "turn_b_act": "PROCEED",
        "turn_b_record": {"subject": "total", "claim": "12"},
        "turn_b_raw": "ACT: PROCEED\nRECORD: total = 12\nCAVEAT: synthetic data, two suppressed",
        "turn_b_attempts": 1,
        "turn_b_entry": {"ts": "2026-11-10T21:05:00+00:00", "caveat_lines": 1},
        "malformed": None,
        "turn_a_skipped": False,
        "last_error": None,
    }
    return {**row, **kw}


def _steps(row: dict[str, Any], recorded: list[str] | None = None) -> list[office_sync.NewStep]:
    return office_sync.steps_to_record(row, recorded or [], starter="Ivan Green", run_ref=RUN)


def test_a_finished_task_is_all_seven_steps_with_the_offices_times() -> None:
    steps = _steps(_row())
    assert [s.step for s in steps] == list(STEPS)
    filed, claimed, turn_a, proposed, approved, forge, turn_b = steps
    assert filed.actor == "Ivan Green"
    assert filed.payload == {"facts": "Which buyers fit deal d-1?", "request": {"deal_id": "d-1"}}
    assert claimed.actor == claimed.agent_id == "Ronan Valek"
    assert turn_a.payload == {"act": "PROCEED", "record": None, "caveats": []}
    assert turn_a.at == datetime(2026, 11, 10, 21, 2)  # naive UTC, as the record stores it
    assert proposed.sandbox_ids == {"office_task": "t-1", "office_run": RUN, "proposal": "p-1"}
    assert approved.actor == SANDBOX_APPROVER
    assert forge.payload == {"status": 200, "total": 12, "suppressed": 2, "results": []}
    assert forge.at == datetime(2026, 11, 10, 21, 4)
    assert turn_b.payload == {
        "act": "PROCEED",
        "record": {"subject": "total", "claim": "12"},
        "caveats": ["synthetic data, two suppressed"],
    }


def test_only_the_steps_not_yet_recorded_are_returned() -> None:
    assert [s.step for s in _steps(_row(), list(STEPS[:4]))] == list(STEPS[4:])
    assert _steps(_row(), list(STEPS)) == []


def test_a_gap_stops_the_list() -> None:
    """Waiting for approval: nothing after the proposal is guessed."""
    row = _row(
        proposal_status="pending",
        decided_at=None,
        decided_by_origin=None,
        forge_status=None,
        turn_b_act=None,
        turn_b_entry=None,
        status="awaiting_approval",
    )
    assert [s.step for s in _steps(row)] == list(STEPS[:4])
    unclaimed = _row(claimed_at=None, agent_name=None, status="open")
    assert [s.step for s in _steps(unclaimed)] == ["filed"]


def test_a_turn_a_other_than_proceed_ends_the_steps() -> None:
    row = _row(turn_a_act="ESCALATE", proposal_id=None, proposal_at=None, status="escalated")
    steps = _steps(row)
    assert [s.step for s in steps] == ["filed", "claimed", "turn_a"]
    assert steps[-1].payload["act"] == "ESCALATE"


def test_an_answer_that_broke_the_grammar_twice_is_unreadable_with_its_rule() -> None:
    malformed = [
        {
            "audit_id": 1,
            "ts": "2026-11-10T21:02:00+00:00",
            "turn": "A",
            "attempt": 1,
            "reason": "answered_with_more_than_one_act_line",
        },
        {
            "audit_id": 2,
            "ts": "2026-11-10T21:02:30+00:00",
            "turn": "A",
            "attempt": 2,
            "reason": "answered_with_no_act_line",
        },
    ]
    row = _row(
        turn_a_act=None,
        turn_a_entry=None,
        malformed=malformed,
        status="escalated",
        proposal_id=None,
        proposal_at=None,
    )
    steps = _steps(row)
    assert steps[-1].step == "turn_a"
    assert steps[-1].payload == {"unreadable": "answered_with_no_act_line"}
    # One bad attempt then a good one: the good one counts.
    retried = _row(malformed=malformed[:1])
    assert _steps(retried)[2].payload["act"] == "PROCEED"


def test_an_approval_by_anyone_but_the_machine_approver_is_passed_on_for_the_record_to_refuse() -> (
    None
):
    row = _row(decided_by_origin="human", decided_by_name="Ivan Green")
    assert _steps(row)[4].actor == "Ivan Green"


def test_the_offices_caveat_count_wins_over_the_text() -> None:
    assert office_sync.caveats("ACT: PROCEED\n**CAVEAT:** one\nCAVEAT: two", 2) == ["one", "two"]
    assert office_sync.caveats("ACT: PROCEED", 1) == ["(caveat 1 of 1, as the Office counted it)"]
    assert office_sync.caveats("ACT: PROCEED\nCAVEAT: x", 0) == []


def test_a_forge_body_that_is_not_an_object_is_kept_under_body() -> None:
    steps = _steps(_row(forge_status=502, forge_body="Bad gateway"))
    assert steps[5].payload == {"status": 502, "body": "Bad gateway"}


def test_the_sql_only_reads() -> None:
    sql = office_sync.OFFICE_TASK_SQL.upper()
    for word in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT"):
        assert not re.search(rf"{word}", sql), word

"""ADR-0166 stage 7: when a sandbox run may start, and when it pauses."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.services.sandbox import rules

MON_10 = datetime(2026, 11, 9, 10, 5)  # a Monday, outside the sweeps
OK = rules.Measured(now=MON_10, free_gb=12.0, exam_open=False)


def _codes(found: list[rules.Refusal]) -> set[str]:
    return {r.code for r in found}


def _hand(**kw: object) -> rules.StartRequest:
    base = {"starter": "Ivan Green", "tasks": 10, "seed_tasks": 20}
    return rules.StartRequest(**{**base, **kw})  # type: ignore[arg-type]


def _schedule(**kw: object) -> rules.Schedule:
    base = {"owner": "Ira Green", "at": "10:05", "tasks": 20, "set_at": "2026-11-09T09:00"}
    return rules.Schedule(**{**base, **kw})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("minute", "inside"),
    [
        (16, False),
        (17, True),
        (24, True),
        (25, False),
        (46, False),
        (47, True),
        (54, True),
        (55, False),
        (0, False),
    ],
)
def test_the_sweeps_are_17_to_24_and_47_to_54_both_ends_inside(minute: int, inside: bool) -> None:
    assert (rules.in_sweep(MON_10.replace(minute=minute)) is not None) is inside


def test_a_sweep_ends_the_minute_after_its_last() -> None:
    assert rules.sweep_ends(MON_10.replace(minute=20, second=30)) == MON_10.replace(minute=25)
    assert rules.sweep_ends(MON_10) == MON_10


def test_a_hand_started_run_passes_when_everything_holds() -> None:
    assert rules.check_start(_hand(), OK) == []


def test_every_reason_is_reported_not_just_the_first() -> None:
    measured = rules.Measured(
        now=MON_10.replace(minute=50),
        free_gb=5.0,
        exam_open=True,
        lock_held_by="pid 1",
        busy_ports=(9212,),
        missing=("the sandbox tables",),
    )
    found = rules.check_start(_hand(starter="Someone Else", tasks=61), measured)
    assert _codes(found) == {
        "not_a_starter",
        "over_task_cap",
        "more_tasks_than_the_seed",
        "inside_a_sweep",
        "exam_open",
        "memory",
        "another_run",
        "port_in_use",
        "missing",
    }


@pytest.mark.parametrize("starter", ["Ivan Green", "Ira Green"])
def test_ivan_or_ira_may_start(starter: str) -> None:
    assert rules.check_start(_hand(starter=starter), OK) == []


def test_sixty_tasks_is_the_cap() -> None:
    assert rules.check_start(_hand(tasks=60, seed_tasks=60), OK) == []
    assert "over_task_cap" in _codes(rules.check_start(_hand(tasks=61, seed_tasks=80), OK))
    assert "over_task_cap" in _codes(rules.check_start(_hand(tasks=0), OK))


def test_free_memory_under_8_gb_refuses() -> None:
    low = rules.Measured(now=MON_10, free_gb=7.9, exam_open=False)
    assert _codes(rules.check_start(_hand(), low)) == {"memory"}
    assert (
        rules.check_start(_hand(), rules.Measured(now=MON_10, free_gb=8.0, exam_open=False)) == []
    )


@pytest.mark.parametrize(
    ("free", "loaded", "exam", "minute", "stop"),
    [
        (5.0, True, False, 5, True),  # the rule's case: unload phi4, then measure again
        (9.0, True, False, 5, False),  # enough memory: leave it
        (5.0, False, False, 5, False),  # nothing to unload
        (5.0, True, True, 5, False),  # an exam is open: never
        (5.0, True, False, 20, False),  # inside a sweep: never
    ],
)
def test_the_phi4_rule(free: float, loaded: bool, exam: bool, minute: int, stop: bool) -> None:
    now = MON_10.replace(minute=minute)
    assert rules.stop_phi4_first(free_gb=free, phi4_loaded=loaded, exam_open=exam, now=now) is stop


def test_a_scheduled_run_is_its_owners_once_a_day_weekends_included() -> None:
    """Ivan Green, 13 November: every day, weekends included; at most once a day."""
    req = _hand(starter="Ira Green", scheduled=True, schedule=_schedule())
    assert rules.check_start(req, OK) == []
    for day in (14, 15):  # Saturday and Sunday
        weekend = rules.Measured(now=datetime(2026, 11, day, 10, 5), free_gb=12, exam_open=False)
        assert rules.check_start(req, weekend) == []
    saturday = rules.Measured(now=datetime(2026, 11, 14, 10, 5), free_gb=12, exam_open=False)
    again_saturday = _hand(
        starter="Ira Green",
        scheduled=True,
        schedule=_schedule(),
        scheduled_today=[datetime(2026, 11, 14, 7, 5)],
    )
    assert _codes(rules.check_start(again_saturday, saturday)) == {"scheduled_run_already_today"}
    # The refusals stay, on a weekend as on any day.
    busy = rules.Measured(now=datetime(2026, 11, 15, 10, 20), free_gb=6, exam_open=True)
    assert _codes(rules.check_start(req, busy)) == {"inside_a_sweep", "exam_open", "memory"}
    again = _hand(
        starter="Ira Green",
        scheduled=True,
        schedule=_schedule(),
        scheduled_today=[MON_10.replace(hour=9)],
    )
    assert _codes(rules.check_start(again, OK)) == {"scheduled_run_already_today"}
    other = _hand(starter="Ivan Green", scheduled=True, schedule=_schedule())
    assert _codes(rules.check_start(other, OK)) == {"not_the_schedule_owner"}


def test_a_stopped_or_missing_schedule_starts_nothing() -> None:
    stopped = _schedule(enabled=False, stopped_at="2026-11-09T09:30", stopped_by="Ira Green")
    req = _hand(starter="Ira Green", scheduled=True, schedule=stopped)
    assert _codes(rules.check_start(req, OK)) == {"schedule_stopped"}
    assert "no_schedule" in _codes(rules.check_start(_hand(scheduled=True), OK))


def test_a_schedule_names_a_starter_a_time_outside_the_sweeps_and_at_most_60() -> None:
    assert rules.check_schedule(_schedule()) == []
    assert _codes(rules.check_schedule(_schedule(owner="Someone"))) == {"not_a_schedule_owner"}
    assert _codes(rules.check_schedule(_schedule(at="10:20"))) == {"schedule_in_a_sweep"}
    assert _codes(rules.check_schedule(_schedule(at="25:00"))) == {"schedule_time_unreadable"}
    assert _codes(rules.check_schedule(_schedule(tasks=61))) == {"over_task_cap"}


def test_a_run_pauses_in_a_sweep_and_while_an_exam_is_open() -> None:
    assert rules.pause_reason(now=MON_10, exam_open=False) is None
    assert "sweep" in (rules.pause_reason(now=MON_10.replace(minute=18), exam_open=False) or "")
    assert "exam" in (rules.pause_reason(now=MON_10, exam_open=True) or "")


def test_removing_a_rule_lets_its_case_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not vacuous: with the sweep check gone, a start inside a sweep is not refused."""
    inside = rules.Measured(now=MON_10.replace(minute=20), free_gb=12, exam_open=False)
    assert "inside_a_sweep" in _codes(rules.check_start(_hand(), inside))
    monkeypatch.setattr(rules, "in_sweep", lambda _now: None)
    assert rules.check_start(_hand(), inside) == []

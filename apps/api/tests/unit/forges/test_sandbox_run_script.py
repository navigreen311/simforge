"""ADR-0166 stage 7: the schedule and stop commands of `scripts.sandbox_run`.

Nothing here registers a Windows task (no `--register`) or starts a run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import sandbox_run
from src.services.sandbox import rules


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("SIMFORGE_SANDBOX_HOME", str(tmp_path))
    return tmp_path


def _schedule(home: Path) -> dict:
    return json.loads((home / "schedule.json").read_text(encoding="utf-8"))


def test_a_schedule_is_set_by_its_owner_and_stopped_only_by_them(home: Path) -> None:
    assert (
        sandbox_run.main(["schedule", "set", "--as", "Ira Green", "--at", "10:05", "--tasks", "20"])
        == 0
    )
    assert _schedule(home)["owner"] == "Ira Green" and _schedule(home)["enabled"] is True
    assert sandbox_run.main(["schedule", "stop", "--as", "Ivan Green"]) == sandbox_run.REFUSED
    assert _schedule(home)["enabled"] is True
    assert sandbox_run.main(["schedule", "set", "--as", "Ivan Green"]) == sandbox_run.REFUSED
    assert sandbox_run.main(["schedule", "stop", "--as", "Ira Green"]) == 0
    stopped = _schedule(home)
    assert stopped["enabled"] is False and stopped["stopped_by"] == "Ira Green"
    # Once stopped, the other starter may set their own.
    assert sandbox_run.main(["schedule", "set", "--as", "Ivan Green", "--at", "09:35"]) == 0


@pytest.mark.parametrize(
    ("args", "code"),
    [
        (["--as", "Someone Else"], sandbox_run.REFUSED),
        (["--as", "Ira Green", "--at", "10:20"], sandbox_run.REFUSED),  # inside a sweep
        (["--as", "Ira Green", "--tasks", "61"], sandbox_run.REFUSED),
    ],
)
def test_a_schedule_outside_the_rules_is_refused(home: Path, args: list[str], code: int) -> None:
    assert sandbox_run.main(["schedule", "set", *args]) == code
    assert not (home / "schedule.json").exists()


def test_without_register_nothing_is_registered(
    home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sandbox_run.main(["schedule", "set", "--as", "Ira Green", "--at", "10:05"])
    out = capsys.readouterr().out
    assert "not registered with Windows" in out and "schtasks /Create" in out
    assert "MON,TUE,WED,THU,FRI" in out
    assert (home / "scheduled-run.cmd").is_file()


def test_stop_asks_the_run_in_progress_to_stop(home: Path) -> None:
    assert sandbox_run.main(["stop", "--as", "Ira Green"]) == 0
    assert sandbox_run.stop_requested().startswith("Ira Green at ")


def test_a_throwaway_run_needs_its_own_database(home: Path) -> None:
    code = sandbox_run.main(["start", "--as", "Ivan Green", "--throwaway"])
    assert code == sandbox_run.REFUSED


def test_a_schedule_runs_at_07_05_from_seed_4_by_default(home: Path) -> None:
    """Generator 1.3.0: each scheduled run takes the next seed no run has used, from 4 (seeds 0
    to 3 were run by hand on 1.2.0), at 07:05 unless told otherwise: before the morning's exams,
    and outside the sweeps."""
    assert sandbox_run.main(["schedule", "set", "--as", "Ivan Green"]) == 0
    written = _schedule(home)
    assert (written["at"], written["seed"], written["tasks"]) == ("07:05", 4, None)
    schedule = sandbox_run.read_schedule()
    assert rules.scheduled_seed(schedule, 0) == 4
    assert rules.scheduled_seed(schedule, 4) == 4
    assert rules.scheduled_seed(schedule, 9) == 9
    later = rules.Schedule(owner="Ivan Green", at="07:05", tasks=None, set_at="x", seed=20)
    assert rules.scheduled_seed(later, 9) == 20
    # A schedule written before 1.3.0 has no first seed: it starts at 4 too.
    assert (
        rules.first_seed(rules.Schedule(owner="Ivan Green", at="07:05", tasks=None, set_at="x"))
        == 4
    )


def test_show_gives_the_next_run_time_and_the_next_seed(
    home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sandbox_run.main(["schedule", "set", "--as", "Ivan Green"])
    monkeypatch.setattr(sandbox_run, "_next_run_time", lambda: "11/16/2026 7:05:00 AM")

    async def next_seed(_schedule: object) -> int:
        return 6

    monkeypatch.setattr(sandbox_run, "_next_scheduled_seed", next_seed)
    capsys.readouterr()
    assert sandbox_run.main(["schedule", "show"]) == 0
    out = capsys.readouterr().out
    assert "next run (Task Scheduler): 11/16/2026 7:05:00 AM" in out
    assert "next seed: 6" in out

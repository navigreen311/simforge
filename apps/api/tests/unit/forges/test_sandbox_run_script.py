"""ADR-0166 stage 7: the schedule and stop commands of `scripts.sandbox_run`.

Nothing here registers a Windows task (no `--register`) or starts a run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import sandbox_run


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

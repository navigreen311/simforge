"""ADR-0167 stage 1: when `grade_now` refuses, and that every grader takes the model's lock."""

from __future__ import annotations

import inspect
import re
from datetime import datetime
from pathlib import Path

import pytest

from scripts import grade_now, resit_partition, run_battery_sweep
from src.services.agent_runtime import exam_model_lock
from src.services.cadence import jobs
from src.workers import partition_sweep

API = Path(__file__).resolve().parents[2]
QUIET = grade_now.Machine(now=datetime(2026, 11, 14, 10, 5), free_gb=12.0)


def _with(**kw: object) -> grade_now.Machine:
    return grade_now.Machine(**{**QUIET.__dict__, **kw})


def test_a_quiet_machine_is_graded_on() -> None:
    assert grade_now.check_machine(QUIET) == []


@pytest.mark.parametrize("minute", [17, 20, 24, 47, 50, 54])
def test_the_sweeps_keep_their_slots(minute: int) -> None:
    found = grade_now.check_machine(_with(now=datetime(2026, 11, 14, 10, minute)))
    assert len(found) == 1 and "sweep keeps its slot" in found[0]


@pytest.mark.parametrize("minute", [16, 25, 46, 55])
def test_outside_the_windows_is_not_a_sweep(minute: int) -> None:
    assert grade_now.check_machine(_with(now=datetime(2026, 11, 14, 10, minute))) == []


def test_a_sandbox_run_a_loaded_model_or_low_memory_refuses() -> None:
    found = grade_now.check_machine(
        _with(sandbox_held_by=("the throwaway slot (pid 1)",), loaded=("phi4:latest",), free_gb=6)
    )
    assert [f.split(":")[0] for f in found] == [
        "a sandbox run is active",
        "Ollama has phi4",
        "6.0 GB free, under 8 GB",
    ]


def test_a_refusal_exits_2_before_any_database_is_opened(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import src.db

    def no_db() -> None:
        raise AssertionError("a refusal opened the database")

    monkeypatch.setattr(src.db, "SessionLocal", no_db)
    busy = _with(loaded=("phi4:latest",))
    assert grade_now.main(["--run-ref", "x"], machine=lambda: busy) == grade_now.REFUSED
    assert "refused, nothing graded" in capsys.readouterr().err


def test_it_is_no_route() -> None:
    """ADR-0050: nothing under src/ imports the operator's script."""
    pattern = re.compile(r"^\s*(from scripts(\.grade_now)? import|import scripts)", re.M)
    hits = [
        p.relative_to(API / "src").as_posix()
        for p in (API / "src").rglob("*.py")
        if pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert hits == []


@pytest.mark.parametrize(
    "grader",
    [
        jobs.battery_sweep,
        partition_sweep.run_partition_pass,
        resit_partition.resit,
        run_battery_sweep.main_async,
        grade_now.grade_run,
        grade_now.grade_partition_now,
    ],
)
def test_every_grader_takes_the_examiners_model_lock(grader: object) -> None:
    src = inspect.getsource(grader)  # type: ignore[arg-type]
    assert "exam_model_lock(" in src


def test_the_model_lock_is_one_key_for_every_grader() -> None:
    assert exam_model_lock.LOCK_KEY == "exam:model"
    src = inspect.getsource(exam_model_lock)
    assert "pg_try_advisory_lock" in src and "pg_advisory_lock(" not in src, "try, never block"


def test_grade_now_calls_what_the_sweeps_call() -> None:
    run = inspect.getsource(grade_now.grade_run)
    assert "submit_battery_result(" in run and "seed=0" in run
    assert "build_exam_runtime(" in run
    part = inspect.getsource(grade_now.grade_partition_now)
    assert "examiner_runtime(" in part
    assert "limit=PARTITION_SWEEP_LIMIT" in part
    assert "budget_seconds=partition_grading.PARTITION_AGENT_BUDGET_SECONDS" in part


def test_run_battery_sweep_uses_the_examiner() -> None:
    src = inspect.getsource(run_battery_sweep)
    assert "build_exam_runtime(" in src and "get_llm_provider" not in src

"""A run that never finished resolves to TIMEOUT, and TIMEOUT never resolves to PASS."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.services.operation.run_window import (
    DEFAULT_RUN_WINDOW_MINUTES,
    TIMEOUT_VERDICT,
    assess_run_window,
    timed_out_run_filter,
)
from src.services.operation.state_machine import OperationState, is_assignable

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def test_a_run_past_its_window_with_no_result_times_out() -> None:
    verdict = assess_run_window(
        started_at=NOW - timedelta(minutes=DEFAULT_RUN_WINDOW_MINUTES + 1),
        ended_at=None,
        now=NOW,
    )

    assert verdict.timed_out is True
    assert verdict.verdict == TIMEOUT_VERDICT
    assert verdict.state == OperationState.IN_TRAINING.value
    assert "never to certified" in verdict.reason


def test_a_timed_out_run_is_never_assignable() -> None:
    """The property Part 10.1 actually cares about."""
    verdict = assess_run_window(
        started_at=NOW - timedelta(hours=99), ended_at=None, now=NOW
    )

    assert verdict.state != OperationState.CERTIFIED.value
    assert not is_assignable(verdict.state or OperationState.NEVER_CERTIFIED.value)


def test_a_timed_out_run_is_not_recorded_as_a_failure() -> None:
    """`failed` means the agent ran and did not pass. A cut-off run proved nothing.

    Recording it as a failure both defames the agent and pollutes the metric that is
    supposed to show real failures — the same not-run-versus-failed distinction the
    state machine exists to hold.
    """
    verdict = assess_run_window(
        started_at=NOW - timedelta(hours=99), ended_at=None, now=NOW
    )

    assert verdict.state != OperationState.FAILED.value


def test_a_run_still_inside_its_window_has_no_verdict_yet() -> None:
    verdict = assess_run_window(
        started_at=NOW - timedelta(minutes=10), ended_at=None, now=NOW
    )

    assert verdict.timed_out is False
    assert verdict.verdict is None
    assert verdict.state is None


def test_a_finished_run_never_times_out_however_slow_it_was() -> None:
    """Timing out is about the absence of a result, not about slowness.

    A battery that took six hours and produced an outcome has an outcome, and that
    outcome is the verdict.
    """
    started = NOW - timedelta(hours=6)
    verdict = assess_run_window(started_at=started, ended_at=NOW, now=NOW)

    assert verdict.timed_out is False
    assert verdict.verdict is None
    assert verdict.minutes_elapsed == 360.0


def test_the_cutoff_is_the_window_before_now() -> None:
    cutoff = timed_out_run_filter(NOW, window_minutes=60)
    assert cutoff == NOW - timedelta(minutes=60)

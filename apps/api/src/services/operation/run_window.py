"""Run windows, and the verdict a run that never finished resolves to.

THE GAP THIS CLOSES
===================

    The Office's `certification.VERDICT_TO_STATE` maps ``TIMEOUT -> in_training`` so
    that a run which did not finish can never certify. Part 10.1 is explicit that
    TIMEOUT must never resolve to PASS.

    That mapping was correct and unreachable. **SimForge emitted no TIMEOUT.** Its
    outbound shape carries states, not verdicts, and none of them meant "this did not
    finish" — so a hung battery produced no verdict at all. Not a timeout resolving to
    a pass; a timeout resolving to *nothing*, silently, with the previous certification
    left in place.

WHY BOTH SIDES HOLD A DEADLINE
==============================

    This module is SimForge reporting a run it can observe exceeding its window. The
    Office additionally holds its own deadline on unanswered submissions
    (``broker/simforge.overdue_submissions``), and that is not redundancy for its own
    sake: **a worker that has died cannot report that it has died.** The case where
    SimForge is the one that failed is exactly the case where SimForge's own detector
    is not running.

    So: SimForge reports what it can see, The Office catches what SimForge cannot
    report, and neither is asked to be the only check.

WHAT A TIMED-OUT RUN IS NOT
===========================

    It is not a failure. ``failed`` means the agent ran and did not pass; a run that
    was cut off proved nothing about the agent at all, and recording it as a failure
    both defames the agent and pollutes the metric that is supposed to show real
    failures. It resolves to ``in_training`` — the state that means "not certified, and
    a battery is what resolves it".

    It also carries no score. Zero would be the tempting default and is a claim about
    the agent rather than about the run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.services.operation.gate_verdict import GateVerdict
from src.services.operation.state_machine import OperationState

#: How long an operation battery may run before it is treated as timed out.
#:
#: Deliberately generous. Resolving a still-running battery to ``in_training`` is
#: harmless — it already is in training — while resolving one too eagerly churns
#: certifications and teaches operators to ignore the state.
DEFAULT_RUN_WINDOW_MINUTES = 180

#: The verdict SimForge reports to The Office for a run that exceeded its window.
#: The Office maps it to ``in_training``; the mapping is asserted from both sides in
#: ``tests/contract/test_office_vocabulary_contract.py``. Aliased from the outbound
#: vocabulary rather than re-spelled, so there is one definition of the string.
TIMEOUT_VERDICT = GateVerdict.TIMEOUT.value


@dataclass(frozen=True, slots=True)
class RunWindowVerdict:
    """What a run's clock says about it.

    ``verdict`` is None for a run that is still inside its window: an unfinished run
    that has not exceeded anything has no verdict yet, and inventing one would be the
    same mistake in the other direction.
    """

    timed_out: bool
    verdict: str | None
    state: str | None
    minutes_elapsed: float
    window_minutes: int
    reason: str


def assess_run_window(
    *,
    started_at: datetime,
    ended_at: datetime | None,
    now: datetime,
    window_minutes: int = DEFAULT_RUN_WINDOW_MINUTES,
) -> RunWindowVerdict:
    """Decide whether a run has exceeded its window.

    A run that ENDED is never timed out, whatever its duration: it produced an outcome,
    and that outcome is the verdict. Timing out is about the absence of a result, not
    about slowness.
    """
    elapsed = (now - started_at).total_seconds() / 60.0

    if ended_at is not None:
        return RunWindowVerdict(
            timed_out=False,
            verdict=None,
            state=None,
            minutes_elapsed=(ended_at - started_at).total_seconds() / 60.0,
            window_minutes=window_minutes,
            reason="run finished; its own outcome is the verdict",
        )

    if elapsed <= window_minutes:
        return RunWindowVerdict(
            timed_out=False,
            verdict=None,
            state=None,
            minutes_elapsed=elapsed,
            window_minutes=window_minutes,
            reason="run is still inside its window and has no verdict yet",
        )

    return RunWindowVerdict(
        timed_out=True,
        verdict=TIMEOUT_VERDICT,
        # Never `failed`: a run that was cut off proved nothing about the agent.
        state=OperationState.IN_TRAINING.value,
        minutes_elapsed=elapsed,
        window_minutes=window_minutes,
        reason=(
            f"run has been open {elapsed:.0f} minutes against a {window_minutes}-minute "
            "window with no result. Reported as TIMEOUT, which resolves to in_training "
            "and never to certified."
        ),
    )


def timed_out_run_filter(
    now: datetime, window_minutes: int = DEFAULT_RUN_WINDOW_MINUTES
) -> datetime:
    """The `startedAt` cutoff for a timed-out run.

    Returned as a value rather than applied as a query so the caller composes it into
    its own `select(Run).where(Run.endedAt.is_(None), Run.startedAt < cutoff)` — this
    module owns the rule, not the query.
    """
    return now - timedelta(minutes=window_minutes)

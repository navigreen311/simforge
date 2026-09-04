"""The queries behind the run window: open a battery, close it, sweep the ones that hung.

`run_window` owns the RULE and touches no database — its own docstring says so. This
module owns the rows, and is the half that makes the rule reachable: a rule about runs
that never finished is worth nothing until something records that a run started.

WHAT THE SWEEP DOES AND DELIBERATELY DOES NOT DO
================================================

    It stamps the run TIMEOUT so SimForge has an answer to give when The Office asks.

    It does NOT rewrite the unit's certification. A unit that was legitimately
    `certified` and whose RE-cert battery hung still holds a certification it earned —
    the hung run failed to produce a new verdict, which is not evidence against the old
    one. Voiding it would also be an illegal transition: `state_machine` allows
    `certified` to move only to `stale_*` or `revoked`, and for good reason. The Office
    resolves TIMEOUT to `in_training` for the SUBMISSION it is waiting on; that is the
    grant-side decision, and it belongs there.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_run import OperationRun
from src.services.operation.gate_verdict import (
    GateVerdict,
    verdict_for_finished_state,
    weakest_state,
)
from src.services.operation.run_window import (
    DEFAULT_RUN_WINDOW_MINUTES,
    assess_run_window,
    timed_out_run_filter,
)
from src.utils.time import utcnow


def _naive_utc(moment: datetime | None) -> datetime:
    """Persisted timestamps are naive UTC (see `utils.time`). Comparing one against a
    tz-aware `now` raises, so callers that pass an aware value are normalised here rather
    than at every comparison."""
    if moment is None:
        return utcnow()
    return moment.replace(tzinfo=None) if moment.tzinfo is not None else moment


async def open_run(
    session: AsyncSession,
    *,
    run_ref: str,
    unit: str,
    forge_id: str,
    instruction_content_hash: str,
    rubric_kind: str,
    rubric_version: str,
    module_id: str | None = None,
    agent_id: str | None = None,
    department_id: str | None = None,
    scenario_count: int = 0,
    coverage_denominator: int = 0,
    window_minutes: int = DEFAULT_RUN_WINDOW_MINUTES,
    started_at: datetime | None = None,
) -> OperationRun:
    """Record that a battery started. Idempotent on `run_ref`.

    Re-opening an existing ref returns the row untouched rather than restarting its
    clock: a retried hand-over must not extend the window of a run that is already
    hanging, which is exactly the case that would hide the timeout.
    """
    existing = (
        await session.execute(select(OperationRun).where(OperationRun.runRef == run_ref))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    run = OperationRun(
        runRef=run_ref,
        unit=unit,
        forgeId=forge_id,
        moduleId=module_id,
        agentId=agent_id,
        departmentId=department_id,
        instructionContentHash=instruction_content_hash,
        rubricKind=rubric_kind,
        rubricVersion=rubric_version,
        startedAt=_naive_utc(started_at),
        windowMinutes=window_minutes,
        scenarioCount=scenario_count,
        coverageDenominator=coverage_denominator,
    )
    session.add(run)
    await session.flush()
    return run


async def close_run(
    session: AsyncSession,
    *,
    run_ref: str,
    agent_states: list[str],
    department_states: list[str],
    score: float | None = None,
    threshold: float | None = None,
    certified_tier: str | None = None,
    scenario_count: int | None = None,
    coverage_denominator: int | None = None,
    ended_at: datetime | None = None,
) -> OperationRun | None:
    """Close the run `gate-result` just reported on. Returns None if no run was opened.

    The run's OWN `unit` decides which outcomes are its own — a Unit A run reports the
    agent states and a Unit B run the department states, and neither borrows the other's.
    Several units can certify under one `run_ref`, and The Office reads a single verdict
    for it, so the weakest wins: a run that certified four agents and failed the fifth is
    not a PASS. Ranking is `gate_verdict.weakest_state`.

    A result arriving for a run already stamped TIMEOUT is still recorded — the verdict
    becomes the real outcome, because a result that ARRIVED is better evidence than a
    deadline that passed. `timedOutAt` is left in place so the late arrival stays
    visible rather than being tidied away.

    Returns the run unchanged if the report carries no outcome for its unit: an empty
    report closes nothing, and stamping a verdict from zero outcomes would invent one.
    """
    run = (
        await session.execute(select(OperationRun).where(OperationRun.runRef == run_ref))
    ).scalar_one_or_none()
    if run is None:
        return None

    own_states = agent_states if run.unit == "A" else department_states
    state = weakest_state(own_states)
    if state is None:
        return run

    run.endedAt = _naive_utc(ended_at)
    run.verdict = verdict_for_finished_state(state)
    run.score = score
    run.threshold = threshold
    run.certifiedTier = certified_tier
    if scenario_count is not None:
        run.scenarioCount = scenario_count
    if coverage_denominator is not None:
        run.coverageDenominator = coverage_denominator
    await session.flush()
    return run


async def sweep_timed_out_runs(
    session: AsyncSession, *, now: datetime | None = None
) -> list[OperationRun]:
    """Stamp every open run that has exceeded ITS OWN window as TIMEOUT.

    Each row is judged against `windowMinutes` as it was recorded, not against the
    current default — changing the default must not retroactively time out a run that
    was inside the window it started under. A single SQL cutoff cannot express that, so
    the cutoff below is only a pre-filter (built from the shortest window in the open
    set, so it can never exclude a row that has genuinely timed out) and the verdict is
    decided per row by `assess_run_window`.
    """
    moment = _naive_utc(now)

    still_open = (OperationRun.endedAt.is_(None), OperationRun.verdict.is_(None))
    shortest = (
        await session.execute(select(func.min(OperationRun.windowMinutes)).where(*still_open))
    ).scalar_one_or_none()
    if shortest is None:
        return []

    cutoff = timed_out_run_filter(moment, window_minutes=int(shortest))
    candidates = (
        (
            await session.execute(
                select(OperationRun).where(*still_open, OperationRun.startedAt < cutoff)
            )
        )
        .scalars()
        .all()
    )

    timed_out: list[OperationRun] = []
    for run in candidates:
        window = assess_run_window(
            started_at=run.startedAt,
            ended_at=run.endedAt,
            now=moment,
            window_minutes=run.windowMinutes,
        )
        if not window.timed_out:
            continue
        run.verdict = GateVerdict.TIMEOUT.value
        run.timedOutAt = moment
        # No score. Zero would be a claim about the agent rather than about the run.
        run.score = None
        run.certifiedTier = None
        timed_out.append(run)

    if timed_out:
        await session.flush()
    return timed_out


async def gate_result_for(
    session: AsyncSession, run_ref: str, *, now: datetime | None = None
) -> dict | None:
    """The body The Office reads. None if SimForge has no record of this ref.

    Every key here is enumerated in The Office's `simforge_response_manifest.json`; a
    field that is not in that manifest fails their `validate_response` on arrival, so
    this dict is written to the manifest and nothing is added to it casually.

    An unknown ref returns None rather than a `NOT_RUN` body, because a NOT_RUN body
    would have to invent a `unit` and a `rubric_version` for a run SimForge never
    received — a shape-valid answer built out of guesses. The caller turns it into a 404.
    """
    run = (
        await session.execute(select(OperationRun).where(OperationRun.runRef == run_ref))
    ).scalar_one_or_none()
    if run is None:
        return None

    moment = _naive_utc(now)
    if run.verdict is not None:
        verdict = run.verdict
    else:
        window = assess_run_window(
            started_at=run.startedAt,
            ended_at=run.endedAt,
            now=moment,
            window_minutes=run.windowMinutes,
        )
        # An open run past its window reads as TIMEOUT even before the sweep has stamped
        # it: the answer must not depend on how recently a background job ran.
        verdict = (
            GateVerdict.TIMEOUT.value if window.timed_out else GateVerdict.IN_PROGRESS.value
        )

    body: dict = {
        "run_ref": run.runRef,
        "unit": run.unit,
        "verdict": verdict,
        "rubric_kind": run.rubricKind,
        "rubric_version": run.rubricVersion,
        "scenario_count": run.scenarioCount,
        "coverage_denominator": run.coverageDenominator,
    }
    # Omitted rather than sent as null when absent: a timed-out run has no score and no
    # completion, and a null in a numeric field invites being read as a zero.
    if run.score is not None:
        body["score"] = run.score
    if run.threshold is not None:
        body["threshold"] = run.threshold
    if run.certifiedTier is not None:
        body["certified_tier"] = run.certifiedTier
    if run.endedAt is not None:
        body["completed_at"] = run.endedAt.isoformat()
    return body

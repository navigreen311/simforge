"""Live (async) scenario execution for the run monitor.

A launch creates the Run row as `queued` and returns immediately; a background task then executes it
with incremental persistence (transcript + trace committed per step) and status transitions
queued → running → scoring → passed/failed/errored, so a watcher can poll progress in real time. The
synchronous run path is unchanged — this only wraps the same executor with a background task + live
flag. Nothing here certifies anyone; running is separate from certification.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from src.config import settings
from src.db import SessionLocal
from src.models.agent import Agent
from src.models.pack import Pack, Scenario
from src.models.run import Run
from src.services.runner.execute import (
    _OUTCOME_STATUS,
    _execute_into_run,
    resolve_run_context,
)
from src.services.village.reader import VillageReader
from src.telemetry.logging import get_logger

log = get_logger("live_run")

# Keep strong refs to background tasks so they aren't garbage-collected mid-run.
_tasks: set[asyncio.Task] = set()

_LEVELS = ("L1", "L2", "L3", "L4", "L5")
# Advisory only (no formal tier→autonomy policy exists): the tier a scenario tests vs the tested
# agent's autonomy. Used to WARN, never to block — running a scenario is a test.
_TIER_MIN_AUTONOMY = {"foundational": 1, "intermediate": 2, "advanced_crisis": 3}


def _autonomy_rank(level: str) -> int:
    return _LEVELS.index(level) + 1 if level in _LEVELS else 1


async def launch_live_run(
    session: AsyncSession, scenario_id: str, *, integrated: bool, actor: str
) -> dict:
    """Create a queued run + start its background execution. Returns the run id + warnings."""
    scenario, pack, agent, use_integrated = await resolve_run_context(
        session, scenario_id, integrated
    )
    run = Run(
        runId=str(ULID()),
        scenarioId=scenario.id,
        packId=pack.id,
        agentId=agent.id,
        executionMode="integrated" if use_integrated else "sandbox",
        narrativeMode=pack.narrativeModeDefault,
        blindMode=False,
        status="queued",
        startedAt=datetime.now(UTC),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    warnings: list[str] = []
    if _autonomy_rank(agent.currentAutonomyLevel) < _TIER_MIN_AUTONOMY.get(scenario.tier, 1):
        warnings.append(
            f"Scenario tier '{scenario.tier}' is above {agent.villageAgentId}'s autonomy "
            f"{agent.currentAutonomyLevel}. Running anyway — this is a test, not a promotion."
        )

    log.info(
        "live_run_launched",
        run_id=run.runId,
        scenario=scenario_id,
        agent=agent.villageAgentId,
        integrated=use_integrated,
        by=actor,
    )
    task = asyncio.create_task(_execute_live(run.runId))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {
        "run_id": run.runId,
        "warnings": warnings,
        "agent_village_id": agent.villageAgentId,
        "integrated": use_integrated,
    }


async def _execute_live(run_id: str) -> None:
    """Background task: run the scenario with incremental persistence, then score it."""
    async with SessionLocal() as session:
        run = (
            await session.execute(select(Run).where(Run.runId == run_id))
        ).scalar_one_or_none()
        if run is None:
            return
        try:
            scenario = (
                await session.execute(select(Scenario).where(Scenario.id == run.scenarioId))
            ).scalar_one()
            pack = (
                await session.execute(select(Pack).where(Pack.id == run.packId))
            ).scalar_one()
            agent = (
                await session.execute(select(Agent).where(Agent.id == run.agentId))
            ).scalar_one()
            reader = VillageReader(village_data_path=Path(settings.village_data_path))

            run.status = "running"
            await session.commit()

            await _execute_into_run(
                session,
                run,
                scenario,
                pack,
                agent,
                reader,
                provider=None,
                use_integrated=run.executionMode == "integrated",
                live=True,
            )

            # Score (a visible transient state), then settle back to the execution outcome.
            if run.status != "errored":
                run.status = "scoring"
                await session.commit()
                from src.services.evaluation import evaluate_run
                from src.services.narrative import apply_narrative_effects
                from src.services.reporter import emit_reports

                card = await evaluate_run(session, run.id)
                await emit_reports(session, run.id)
                await apply_narrative_effects(session, run, card)
                run.status = _OUTCOME_STATUS.get(run.outcome or "", "errored")
                await session.commit()
        except Exception as exc:  # noqa: BLE001 — a failed run is data; never crash the task
            log.warning("live_run_failed", run_id=run_id, error=str(exc))
            run.status = "errored"
            run.outcome = run.outcome or f"error: {type(exc).__name__}"
            run.endedAt = datetime.now(UTC)
            await session.commit()

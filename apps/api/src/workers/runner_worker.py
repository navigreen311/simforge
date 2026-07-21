"""Scenario runner worker (blueprint §C.5, queue `runs`).

Production async execution path: `POST /scenarios/{id}/run` enqueues `run_scenario_job`;
the RQ worker executes it. (Phase 4 also supports inline execution for the dev demo.)
"""

from __future__ import annotations

import asyncio

from src.db import SessionLocal, dispose_engine
from src.services.runner import run_scenario
from src.services.village.reader import VillageReader
from src.telemetry.logging import get_logger

log = get_logger("runner_worker")


async def _run(scenario_id: str) -> str:
    reader = VillageReader.from_settings()
    async with SessionLocal() as session:
        run = await run_scenario(session, scenario_id, reader)
    log.info("scenario_run_complete", run_id=run.runId, status=run.status, outcome=run.outcome)
    await dispose_engine()
    return run.runId


def run_scenario_job(scenario_id: str) -> str:
    """Synchronous entrypoint for RQ."""
    return asyncio.run(_run(scenario_id))

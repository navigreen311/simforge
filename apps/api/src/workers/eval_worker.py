"""Evaluation worker (blueprint §C.5, queue `eval`).

Async path: a completed run is enqueued; the worker evaluates it and persists the
Scorecard. (Phase 5 also evaluates inline in the run endpoint for the dev demo.)
"""

from __future__ import annotations

import asyncio

from src.db import SessionLocal, dispose_engine
from src.services.evaluation import evaluate_run
from src.telemetry.logging import get_logger

log = get_logger("eval_worker")


async def _run(run_internal_id: str) -> str:
    async with SessionLocal() as session:
        card = await evaluate_run(session, run_internal_id)
    log.info(
        "run_evaluated",
        run_internal_id=run_internal_id,
        gate_passed=card.readinessGatePassed,
        auto_fail=card.autoFailReason,
    )
    await dispose_engine()
    return card.id


def evaluate_run_job(run_internal_id: str) -> str:
    """Synchronous entrypoint for RQ."""
    return asyncio.run(_run(run_internal_id))

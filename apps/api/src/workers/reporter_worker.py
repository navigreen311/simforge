"""Reporter worker (blueprint §C.5, queue `reports`).

Async path: after a run's Scorecard is saved, emit the Software + Village-OS gap reports.
(Phase 6 also emits inline in the run endpoint for the dev demo.)
"""

from __future__ import annotations

import asyncio

from src.db import SessionLocal, dispose_engine
from src.services.reporter import emit_reports
from src.telemetry.logging import get_logger

log = get_logger("reporter_worker")


async def _run(run_internal_id: str) -> dict:
    async with SessionLocal() as session:
        result = await emit_reports(session, run_internal_id)
    log.info(
        "reports_emitted",
        run_internal_id=run_internal_id,
        software_gaps=result.software_gaps,
        village_os_gaps=result.village_os_gaps,
    )
    await dispose_engine()
    return {"software_gaps": result.software_gaps, "village_os_gaps": result.village_os_gaps}


def emit_reports_job(run_internal_id: str) -> dict:
    """Synchronous entrypoint for RQ."""
    return asyncio.run(_run(run_internal_id))

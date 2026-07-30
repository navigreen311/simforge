"""In-process cadence scheduler (Part 16).

An AsyncIOScheduler that fires the registered cadence jobs on their cron schedule. Started from the
app lifespan ONLY when `settings.scheduler_enabled` (default off) so CI/tests and single-shot runs
never spin it up. The job registry (services/cadence/registry.py) is the single source of truth for
the schedule; this module just wires each job's async core to an APScheduler cron trigger.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import settings
from src.services.cadence.registry import JOBS
from src.telemetry.logging import get_logger

log = get_logger("scheduler")

_scheduler: AsyncIOScheduler | None = None


def _make_runner(name: str):  # noqa: ANN202 — returns an async closure
    from src.services.cadence.registry import JOBS_BY_NAME

    async def _runner() -> None:
        job = JOBS_BY_NAME[name]
        try:
            result = await job.run()
            log.info("cadence_job_ran", job=name, result=result)
        except Exception as exc:  # noqa: BLE001 — a job failure must not kill the scheduler
            log.error("cadence_job_failed", job=name, error=str(exc))

    return _runner


def start_scheduler() -> AsyncIOScheduler | None:
    """Start the cadence scheduler if enabled; otherwise a no-op. Idempotent."""
    global _scheduler
    if not settings.scheduler_enabled:
        log.info("scheduler_disabled")
        return None
    if _scheduler is not None:
        return _scheduler
    sched = AsyncIOScheduler(timezone="UTC")
    for job in JOBS:
        sched.add_job(
            _make_runner(job.name),
            trigger=CronTrigger(**job.cron, timezone="UTC"),
            id=job.name,
            name=job.name,
            replace_existing=True,
        )
    sched.start()
    _scheduler = sched
    log.info("scheduler_started", jobs=[j.name for j in JOBS])
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def scheduler_running() -> bool:
    return _scheduler is not None and _scheduler.running

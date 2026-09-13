"""Cadence job cores (Part 16 continuous cadence).

Each job is an async function that does its work and returns a summary dict. It accepts an OPTIONAL
session: the on-demand trigger endpoint passes the request's (test-overridable) session; the
APScheduler triggers pass none, so the job opens its own SessionLocal. Jobs degrade gracefully when
the Village reader is unavailable (dev/CI) — a missing reader skips the reader-dependent work rather
than failing the sweep.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from src.db import SessionLocal
from src.services.village.reader import VillageReader, VillageReaderError
from src.telemetry.logging import get_logger

log = get_logger("cadence")

#: Runs scored per battery pass. Eleven live model calls each, so this is a spend ceiling as much
#: as a throughput one: ten is the sweep's own default, restated here because a scheduled caller
#: choosing it silently is how a cost becomes invisible.
BATTERY_SWEEP_LIMIT = 10


@asynccontextmanager
async def _session(session: AsyncSession | None) -> AsyncIterator[AsyncSession]:
    """Use the provided (request) session, or open a fresh one for the scheduler path."""
    if session is not None:
        yield session
        return
    async with SessionLocal() as owned:
        yield owned


async def daily_regression(session: AsyncSession | None = None) -> dict:
    """Detect prior-pass/now-fail flips over existing runs; auto-suspend affected certs (§9.2)."""
    from src.services.evaluation.regression_sweep import find_and_suspend_regressions

    async with _session(session) as s:
        report = await find_and_suspend_regressions(s)
    return {"job": "daily_regression", **report.as_dict()}


async def nightly_cert_lifecycle(session: AsyncSession | None = None) -> dict:
    """Mark past-due certs expired + count those expiring soon (§16.1)."""
    from src.workers.cert_lifecycle_worker import _sweep

    async with _session(session) as s:
        result = await _sweep(s)
    return {"job": "nightly_cert_lifecycle", **result}


async def daily_snapshot(session: AsyncSession | None = None) -> dict:
    """Capture today's cognitive snapshot for every agent (drift baseline; §16.1)."""
    from src.services.cognitive import capture_daily_snapshots

    try:
        reader = VillageReader.from_settings()
    except VillageReaderError as exc:
        log.warning("cadence_snapshot_skipped", error=str(exc))
        return {"job": "daily_snapshot", "skipped": "village_data_unavailable"}
    async with _session(session) as s:
        result = await capture_daily_snapshots(s, reader)
    return {"job": "daily_snapshot", **result}


async def expire_waivers_job(session: AsyncSession | None = None) -> dict:
    """Expire waivers past their TTL (§11.5)."""
    from src.services.governance.waiver import expire_waivers

    async with _session(session) as s:
        expired = await expire_waivers(s)
    return {"job": "expire_waivers", "expired": len(expired)}


async def evidence_purge(session: AsyncSession | None = None) -> dict:
    """Purge evidence records past retention (unless on legal hold) — §12.3."""
    from src.services.evidence import purge_expired

    async with _session(session) as s:
        purged = await purge_expired(s)
    return {"job": "evidence_purge", "purged": len(purged)}


async def safe_mode_auto_trigger(session: AsyncSession | None = None) -> dict:
    """Auto-raise a scoped safe mode when compliance failures spike (§11.7)."""
    from src.services.governance.safe_mode_service import maybe_auto_activate

    async with _session(session) as s:
        row = await maybe_auto_activate(s)
    return {"job": "safe_mode_auto_trigger", "activated": row.id if row else None}


async def hourly_approval_escalation(session: AsyncSession | None = None) -> dict:
    """Expire approval requests past their TTL (§11.5 time-bound auto-escalation)."""
    from src.services.governance.approval import expire_stale_requests

    async with _session(session) as s:
        expired = await expire_stale_requests(s)
    return {"job": "hourly_approval_escalation", "expired": expired, "count": len(expired)}


async def battery_sweep(session: AsyncSession | None = None) -> dict:
    """Put a battery to each unscored Unit-A run, and let each one close its own run.

    **Hourly, not daily, and the interval is not a taste.** A run's default window is
    `DEFAULT_RUN_WINDOW_MINUTES = 180`. A daily sweep would arrive after almost every run had
    already been stamped TIMEOUT, and `unscored_runs` deliberately does not re-score a timed-out
    run - so a daily cadence would make this job a no-op against the very runs it exists to find.
    Hourly leaves a run at worst 60 minutes of its 180 waiting, and at least 120 for a battery
    that the sweep's own docstring warns "can take minutes".

    **The examiner is named in the result because it is not always the one you assume.**
    `LLM_PROVIDER` defaults to `stub`, and `auto` resolves to ollama-if-reachable-else-stub - never
    anthropic. A scheduled pass therefore scores with whatever that resolution produced, unattended.
    The certification itself already records it (`agent_model=provider_label(...)` in
    `battery_for_run`), so this is not silent; surfacing it here means the operator reading the job
    log sees it without opening a cert.

    Degrades the way `daily_snapshot` does: no Village data, no runtime, no pass - a skip rather
    than a 500, because an unreachable reader is a deployment fact and not a sweep failure.
    """
    from src.services.agent_runtime.llm_client import provider_label
    from src.services.agent_runtime.runtime import build_agent_runtime
    from src.workers.battery_sweep import battery_sweep_lock, sweep_unscored_runs

    try:
        reader = VillageReader.from_settings()
    except VillageReaderError as exc:
        log.warning("cadence_battery_sweep_skipped", error=str(exc))
        return {"job": "battery_sweep", "skipped": "village_data_unavailable"}

    runtime = build_agent_runtime(reader)
    # The lock gets its OWN session, and this is not tidiness.
    #
    # `battery_sweep_lock` pins itself to one connection because `pg_advisory_lock` is held by the
    # backend, not the transaction. `sweep_unscored_runs` calls `session.rollback()` for every run
    # whose battery raises - that is the whole point of its `except` - and a rollback hands the
    # connection back. Holding the lock on the swept session therefore means the first failed run
    # closes the connection the unlock needs, and the pass ends in `ResourceClosedError` instead of
    # the outcome it had already computed. Observed, not theorised.
    async with _session(session) as s, SessionLocal() as lock_session:
        async with battery_sweep_lock(lock_session) as acquired:
            if not acquired:
                log.info("cadence_battery_sweep_locked")
                return {"job": "battery_sweep", "skipped": "another_pass_holds_the_lock"}
            outcome = await sweep_unscored_runs(s, runtime=runtime, limit=BATTERY_SWEEP_LIMIT)

    return {
        "job": "battery_sweep",
        "examiner": provider_label(runtime.provider),
        "considered": outcome.considered,
        "scored": outcome.scored,
        "skipped": [list(pair) for pair in outcome.skipped],
        "failed": [list(pair) for pair in outcome.failed],
    }


async def daily_fingerprint(session: AsyncSession | None = None) -> dict:
    """Check the Village schema fingerprint for drift (§16.1)."""
    from src.services.village.fingerprint import capture_fingerprint

    try:
        reader = VillageReader.from_settings()
    except VillageReaderError as exc:
        log.warning("cadence_fingerprint_skipped", error=str(exc))
        return {"job": "daily_fingerprint", "skipped": "village_data_unavailable"}
    async with _session(session) as s:
        result = await capture_fingerprint(s, reader)
    return {
        "job": "daily_fingerprint",
        "fingerprint": result.fingerprint[:12],
        "drift_detected": result.drift_detected,
    }

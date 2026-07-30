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

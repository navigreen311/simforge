"""Nightly Village fingerprint check (blueprint §C.5, queue `fingerprint`, 01:00 UTC).

Captures the current Village schema fingerprint and records drift. On drift, Phase 7
wiring will block new cert issuance and alert (runbook R-006).
"""

from __future__ import annotations

import asyncio

from src.db import SessionLocal
from src.services.village.fingerprint import FingerprintResult, capture_fingerprint
from src.services.village.reader import VillageReader
from src.telemetry.logging import get_logger

log = get_logger("fingerprint_worker")


async def _run() -> FingerprintResult:
    reader = VillageReader.from_settings()
    async with SessionLocal() as session:
        result = await capture_fingerprint(session, reader)
    log.info(
        "village_fingerprint_captured",
        fingerprint=result.fingerprint[:12],
        drift=result.drift_detected,
        newly_recorded=result.newly_recorded,
    )
    return result


def run_fingerprint_check() -> dict:
    """Synchronous entrypoint for RQ."""
    result = asyncio.run(_run())
    return {
        "fingerprint": result.fingerprint,
        "drift_detected": result.drift_detected,
        "previous": result.previous,
    }

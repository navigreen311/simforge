"""Health & readiness router (blueprint §C.3.1). Public (no auth)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_session
from src.schemas.health import FingerprintResponse, HealthResponse, ReadyResponse

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
async def readiness(session: AsyncSession = Depends(get_session)) -> ReadyResponse:
    checks: dict[str, str] = {}

    # DB
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 — readiness surfaces the reason
        checks["database"] = f"error: {type(exc).__name__}"

    # Redis (best-effort; Phase 1 does not hard-require it)
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url)
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {type(exc).__name__}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return ReadyResponse(status=overall, checks=checks)


@router.get("/village-fingerprint", response_model=FingerprintResponse)
async def village_fingerprint() -> FingerprintResponse:
    """Live Village schema fingerprint + drift flag vs the configured expected value."""
    from src.services.village.reader import VillageReader, VillageReaderError

    expected = settings.village_os_version_fingerprint
    try:
        reader = VillageReader.from_settings()
        current = reader.get_village_schema_fingerprint()
    except VillageReaderError:
        # Village data not mounted in this environment — report the configured value.
        return FingerprintResponse(fingerprint=expected, captured_at=None, drift_detected=False)

    drift = expected not in ("", "dev-fingerprint") and current != expected
    return FingerprintResponse(
        fingerprint=current,
        captured_at=datetime.now(UTC).isoformat(),
        drift_detected=drift,
    )

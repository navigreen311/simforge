"""Health & readiness router (blueprint §C.3.1). Public (no auth)."""

from __future__ import annotations

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
    # Phase 2 wires the real VillageReader fingerprint; Phase 1 echoes configured value.
    return FingerprintResponse(
        fingerprint=settings.village_os_version_fingerprint,
        captured_at=None,
        drift_detected=False,
    )

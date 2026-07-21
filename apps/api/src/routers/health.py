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


@router.get("/config")
async def seam_config() -> dict:
    """Non-secret view of which integration seams are in production vs stub mode (ADR-0030).

    A deploy-readiness check: confirm the seams you intend to run for real are actually configured.
    Reports modes only — never keys or secrets."""
    return {
        "app_version": settings.app_version,
        "auth_mode": settings.auth_mode,  # dev-bypass | clerk
        "hsm_provider": settings.hsm_provider,  # stub | file | yubihsm | cloudhsm
        "forge_mode": settings.forge_mode,  # local | http
        "forge_http_sandboxes": sorted(settings.forge_sandbox_urls.keys()),
        "llm_provider": settings.llm_provider,  # stub | ollama | anthropic | auto
        "llm_judge_provider": settings.llm_judge_provider,
        "integrated_execution_enabled": settings.integrated_execution_enabled,
        "linear_enabled": bool(settings.linear_api_key and settings.linear_team_id),
        "all_stub": (
            settings.auth_mode == "dev-bypass"
            and settings.hsm_provider == "stub"
            and settings.forge_mode == "local"
            and settings.llm_provider == "stub"
            and not settings.integrated_execution_enabled
        ),
    }


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

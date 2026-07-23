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
        "tracing_enabled": settings.otel_traces_enabled
        or bool(settings.otel_exporter_otlp_endpoint),
        "tracing_exporter": bool(settings.otel_exporter_otlp_endpoint),  # exports to a collector
        "all_stub": (
            settings.auth_mode == "dev-bypass"
            and settings.hsm_provider == "stub"
            and settings.forge_mode == "local"
            and settings.llm_provider == "stub"
            and not settings.integrated_execution_enabled
        ),
    }


@router.get("/llm-mode")
async def llm_mode() -> dict:
    """Which LLM providers are configured + whether judge scores are stub-derived (ADR-0023).

    Drives the stub-mode banner: `stub_scores` is true when the judge is the deterministic stub
    (or `auto` with no reachable Ollama), meaning P7/C1/C2 are heuristic-only."""
    from src.services.agent_runtime.llm_client import resolve_provider

    judge_effective = resolve_provider(settings.llm_judge_provider)
    agent_effective = resolve_provider(settings.llm_provider)
    return {
        "agent_provider": settings.llm_provider,
        "judge_provider": settings.llm_judge_provider,
        "agent_effective": agent_effective,
        "judge_effective": judge_effective,
        "stub_scores": judge_effective == "stub",
    }


@router.get("/system-status")
async def system_status(session: AsyncSession = Depends(get_session)) -> dict:
    """Consolidated system health for the Overview card: LLM, fingerprint, constitution, HSM."""
    from sqlalchemy import select

    from src.models.governance import Constitution
    from src.services.agent_runtime.llm_client import resolve_provider

    # Active constitution = the one not yet superseded (highest version if several).
    current = (
        await session.execute(
            select(Constitution)
            .where(Constitution.supersededByVersion.is_(None))
            .order_by(Constitution.ratifiedAt.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    fingerprint_status = "unavailable"
    try:
        from src.services.village.reader import VillageReader, VillageReaderError

        try:
            reader = VillageReader.from_settings()
            current_fp = reader.get_village_schema_fingerprint()
            expected = settings.village_os_version_fingerprint
            drift = expected not in ("", "dev-fingerprint") and current_fp != expected
            fingerprint_status = "drift_detected" if drift else "stable"
        except VillageReaderError:
            fingerprint_status = "unavailable"
    except Exception:  # noqa: BLE001 — fingerprint is best-effort, never fails the status call
        fingerprint_status = "unavailable"

    return {
        "llm_provider": settings.llm_provider,
        "llm_judge_provider": settings.llm_judge_provider,
        "llm_judge_effective": resolve_provider(settings.llm_judge_provider),
        "village_fingerprint": fingerprint_status,
        "constitution_version": current.version if current else None,
        "hsm_provider": settings.hsm_provider,  # stub | file | yubihsm | cloudhsm
        "hsm_status": "connected" if settings.hsm_provider != "stub" else "stub",
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

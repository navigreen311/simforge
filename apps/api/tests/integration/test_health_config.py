"""Deploy-readiness: the seam-config endpoint reports modes, never secrets (ADR-0030)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.config import settings


async def test_config_reports_seam_modes_all_stub_by_default(client: AsyncClient) -> None:
    cfg = (await client.get("/api/health/config")).json()
    # Every seam mode is reported.
    for key in (
        "auth_mode",
        "hsm_provider",
        "forge_mode",
        "llm_provider",
        "llm_judge_provider",
        "integrated_execution_enabled",
        "linear_enabled",
        "all_stub",
    ):
        assert key in cfg
    # Shipped default is fully stub/sandbox.
    assert cfg["all_stub"] is True
    assert cfg["integrated_execution_enabled"] is False
    assert cfg["linear_enabled"] is False


async def test_config_reflects_production_seams(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "clerk")
    monkeypatch.setattr(settings, "hsm_provider", "file")
    cfg = (await client.get("/api/health/config")).json()
    assert cfg["auth_mode"] == "clerk" and cfg["hsm_provider"] == "file"
    assert cfg["all_stub"] is False  # a production seam flips it


async def test_config_leaks_no_secrets(client: AsyncClient) -> None:
    cfg = (await client.get("/api/health/config")).json()
    blob = str(cfg).lower()
    for secret_word in ("key", "secret", "password", "pem", "token", "pin"):
        assert secret_word not in blob

"""Monthly cost-cap enforcement (ADR-0039)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.run import Run

REPO_ROOT = Path(__file__).resolve().parents[4]
GREENSTONE = str(REPO_ROOT / "packs" / "greenstone" / "v1")


async def test_budget_status_starts_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/budget/status")
    assert resp.status_code == 200
    modes = resp.json()["modes"]
    assert modes["sandbox"]["spent_usd"] == 0.0
    assert modes["sandbox"]["exceeded"] is False
    assert modes["integrated"]["cap_usd"] == settings.simforge_budget_integrated_monthly_usd


async def test_run_allowed_under_cap(client: AsyncClient) -> None:
    """Stub runs cost 0, so the default cap never trips — runs proceed normally."""
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})
    run = await client.post("/api/scenarios/scn.gs.src.001/run")
    assert run.status_code == 200


async def test_run_blocked_when_cap_reached(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sandbox cap at 0 + a non-zero recorded cost ⇒ new sandbox runs are blocked (402)."""
    await client.post("/api/packs/", json={"pack_dir": GREENSTONE})

    # A first run records this month's sandbox spend (zero-cost under stub) and passes.
    first = await client.post("/api/scenarios/scn.gs.src.001/run")
    assert first.status_code == 200

    # Give the recorded run a real cost and drop the cap to 0 → spend >= cap → exceeded.
    await db_session.execute(update(Run).values(costUsd=1.0))
    await db_session.commit()
    monkeypatch.setattr(settings, "simforge_budget_sandbox_monthly_usd", 0.0)

    status = await client.get("/api/budget/status")
    assert status.json()["modes"]["sandbox"]["exceeded"] is True
    assert status.json()["modes"]["sandbox"]["spent_usd"] == 1.0

    blocked = await client.post("/api/scenarios/scn.gs.src.001/run")
    assert blocked.status_code == 402
    assert "budget exceeded" in blocked.json()["detail"].lower()

"""Cadence scheduler (Part 16): status lists the schedule; jobs trigger on demand."""

from __future__ import annotations

from httpx import AsyncClient


async def test_scheduler_status_lists_jobs(client: AsyncClient) -> None:
    body = (await client.get("/api/scheduler/status")).json()
    assert body["enabled"] is False  # default off in tests
    assert body["running"] is False
    names = {j["name"] for j in body["jobs"]}
    assert {
        "daily_regression",
        "nightly_cert_lifecycle",
        "daily_snapshot",
        "daily_fingerprint",
    } <= names
    for j in body["jobs"]:
        assert j["schedule"] and j["description"]


async def test_trigger_regression_job_on_demand(client: AsyncClient) -> None:
    result = (await client.post("/api/scheduler/run/daily_regression")).json()
    assert result["job"] == "daily_regression"
    assert "scanned_certs" in result and "suspended_cert_ids" in result


async def test_trigger_cert_lifecycle_job_on_demand(client: AsyncClient) -> None:
    result = (await client.post("/api/scheduler/run/nightly_cert_lifecycle")).json()
    assert result["job"] == "nightly_cert_lifecycle"
    assert "expired" in result and "expiring_soon" in result


async def test_snapshot_job_degrades_without_village_data(client: AsyncClient) -> None:
    # In CI the Village data path may be absent → the job skips gracefully, never 500s.
    result = (await client.post("/api/scheduler/run/daily_snapshot")).json()
    assert result["job"] == "daily_snapshot"


async def test_unknown_job_404(client: AsyncClient) -> None:
    resp = await client.post("/api/scheduler/run/nope")
    assert resp.status_code == 404

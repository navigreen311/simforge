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


# --- the battery sweep: scheduled, listed, and not triggerable (ADR-0050) -------------------


async def test_battery_sweep_is_scheduled_and_listed(client: AsyncClient) -> None:
    """It must be visible. Withholding the verb is not the same as hiding the job."""
    body = (await client.get("/api/scheduler/status")).json()
    job = next((j for j in body["jobs"] if j["name"] == "battery_sweep"), None)
    assert job is not None, "the sweep is registered, so /status must say so"
    assert job["schedule"] == "hourly"


async def test_battery_sweep_cannot_be_triggered_by_request(
    client: AsyncClient, monkeypatch
) -> None:
    """ADR-0050: *there is NO endpoint that triggers a battery.*

    The ADR's own guard walks the import graph out of `src.routers.operation` and therefore cannot
    see this router at all. Registering the sweep in the cadence would have passed that walk while
    handing an HTTP verb to the battery — so this is the test that actually holds the rule, and it
    asserts the sweep was not merely refused but never called.
    """
    import src.workers.battery_sweep as sweep_mod

    called = False

    async def _tripwire(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("a request reached the battery")

    monkeypatch.setattr(sweep_mod, "sweep_unscored_runs", _tripwire)

    resp = await client.post("/api/scheduler/run/battery_sweep")
    assert resp.status_code == 403
    assert "ADR-0050" in resp.json()["detail"]
    assert called is False


async def test_refusal_is_403_not_404_so_the_job_stays_visible(client: AsyncClient) -> None:
    """An unknown job and a withheld one are different facts and must not answer alike."""
    assert (await client.post("/api/scheduler/run/nope")).status_code == 404
    assert (await client.post("/api/scheduler/run/battery_sweep")).status_code == 403


async def test_every_other_job_is_still_triggerable() -> None:
    """The flag must not quietly spread. Today exactly one job carries it."""
    from src.services.cadence import JOBS

    assert {j.name for j in JOBS if not j.triggerable} == {"battery_sweep"}


async def test_battery_sweep_hourly_fits_inside_the_run_window() -> None:
    """A daily cadence would make this job a no-op, which is the failure worth a test.

    `unscored_runs` will not re-score a run already stamped TIMEOUT. So a sweep whose interval
    exceeds `DEFAULT_RUN_WINDOW_MINUTES` arrives after the rows it exists to find have left the
    filter — a registered, running, permanently empty sweep.
    """
    from src.services.cadence import JOBS_BY_NAME
    from src.services.operation.run_window import DEFAULT_RUN_WINDOW_MINUTES

    cron = JOBS_BY_NAME["battery_sweep"].cron
    assert set(cron) == {"minute"} and isinstance(cron["minute"], int), (
        "an hourly cron is 'minute only'; any hour/day key means the interval grew"
    )
    assert 60 < DEFAULT_RUN_WINDOW_MINUTES, "hourly must leave headroom inside the window"


async def test_battery_sweep_job_degrades_without_village_data() -> None:
    """No Village reader → skip, never a 500. Same contract as daily_snapshot."""
    from src.services.cadence import jobs

    result = await jobs.battery_sweep()
    assert result["job"] == "battery_sweep"
    if "skipped" not in result:
        assert {"examiner", "considered", "scored"} <= set(result)

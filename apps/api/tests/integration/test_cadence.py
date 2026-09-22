"""Cadence scheduler (Part 16): status lists the schedule; jobs trigger on demand."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert
from src.utils.time import utcnow


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


# ADR-0105. THE THREE TESTS BELOW ASSERTED THE REPORT OVER AN EMPTY DATABASE.
#
# `assert "scanned_certs" in result` was true of a job that returned a literal, and no fixture
# existed for any of them to act on - so `scanned_certs` was 0, `expired` was 0, and the assertion
# could not have failed however the job behaved. Each now sets up a row and asserts that row.
#
# These run the job through its ROUTE, which supplies a request session. The scheduler path, where
# the job opens a session of its own, is a different caller and is covered separately in
# `test_a_job_asserts_its_row.py` - that is the branch `run_timeout_sweep` lost its commit in.


async def test_trigger_regression_job_suspends_the_covering_cert(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A prior-pass/now-fail flip suspends the cert covering the cap."""
    from tests.integration.test_regression_sweep import (
        _greenstone,
        _issue_active_cert,
        _run_with_card,
        _seed_scenario,
    )

    await client.post("/api/packs/", json={"pack_dir": _greenstone()})
    agent, scenario = await _seed_scenario(db_session)
    cert = await _issue_active_cert(db_session, agent)
    cert_id = cert.id  # read BEFORE expire_all below; after it this is a lazy load
    await _run_with_card(db_session, agent, scenario, passed=True, minutes_ago=120)
    await _run_with_card(db_session, agent, scenario, passed=False, minutes_ago=5)
    await db_session.commit()

    result = (await client.post("/api/scheduler/run/daily_regression")).json()

    assert result["job"] == "daily_regression"
    assert cert_id in result["suspended_cert_ids"]
    db_session.expire_all()
    row = (
        await db_session.execute(select(AgentCert).where(AgentCert.id == cert_id))
    ).scalar_one()
    assert row.status == "suspended"


async def test_trigger_cert_lifecycle_job_expires_a_past_due_cert(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """And leaves an expiring-soon one active, which `{"expired": 1}` on its own cannot say."""
    from tests.integration.test_regression_sweep import _greenstone, _issue_active_cert

    await client.post("/api/packs/", json={"pack_dir": _greenstone()})
    agent = (
        await db_session.execute(select(Agent).where(Agent.villageAgentId == "david_kim"))
    ).scalar_one()
    cert = await _issue_active_cert(db_session, agent)
    cert.expiresAt = utcnow() - timedelta(days=1)
    cert_id = cert.id  # read BEFORE expire_all below
    await db_session.commit()

    result = (await client.post("/api/scheduler/run/nightly_cert_lifecycle")).json()

    assert result["job"] == "nightly_cert_lifecycle"
    assert result["expired"] == 1
    db_session.expire_all()
    row = (
        await db_session.execute(select(AgentCert).where(AgentCert.id == cert_id))
    ).scalar_one()
    assert row.status == "expired"


async def test_snapshot_job_degrades_without_village_data(client: AsyncClient) -> None:
    """**Left as a report assertion, and deliberately.** This one is about the degraded path: with
    no Village data the job must skip rather than 500, and a skip has no row to assert. The
    wrapper's session handling is covered in `test_a_job_asserts_its_row.py`; the capture itself
    remains uncovered, because it needs Village data a test cannot supply."""
    result = (await client.post("/api/scheduler/run/daily_snapshot")).json()
    assert result["job"] == "daily_snapshot"
    assert "skipped" in result or "captured" in result


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

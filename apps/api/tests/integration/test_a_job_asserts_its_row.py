"""ADR-0105 — a job's test asserts the row the job changes, from a fresh session, through the
scheduler's own path.

**Measured: `run_timeout_sweep` shipped passing and closed nothing.** Its callee only flushed, the
job never committed, and its test asserted `out["timed_out"] == 1` — true of a job that writes
nothing. Two properties of that test let it through, and both are fixed here for every job:

* it asserted the **return value**, which is a claim about what the job FOUND;
* it passed a **session**, so it never entered the branch APScheduler takes.

`evidence_purge` comes first because it is the destructive one. Then `safe_mode_auto_trigger`,
which runs every fifteen minutes in the live process and had no job-level test at all.

**One correction to the premise, worth stating.** `evidence_purge` does not delete. `purge_expired`
sets `purgedAt` and moves the record to `tier = "cold"` — a tombstone, not a removal, and the
chain-of-custody anchor survives. Which is a better design than the name suggests, and the tests
below assert the tombstone rather than an absence.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.approval import ApprovalRequest
from src.models.cert import AgentCert
from src.models.cognitive_snapshot import CognitiveSnapshot
from src.models.evidence import EvidenceRecord
from src.models.safe_mode import SafeModeState
from src.models.waiver import Waiver
from src.services.evidence import register_evidence, set_legal_hold
from src.utils.time import utcnow
from tests.integration.scheduler_path import fresh_session, run_scheduled

pytestmark = pytest.mark.asyncio


# =================================================================================================
# evidence_purge - FIRST, because it is the one that destroys
# =================================================================================================


async def _evidence(session: AsyncSession, bundle_id: str, *, days_past: int) -> None:
    await register_evidence(
        session, bundle_id=bundle_id, ref=f"file:///{bundle_id}", content_hash=bundle_id
    )
    await session.commit()
    record = (
        await session.execute(
            select(EvidenceRecord).where(EvidenceRecord.bundleId == bundle_id)
        )
    ).scalar_one()
    record.retentionUntil = utcnow() - timedelta(days=days_past)
    await session.commit()


async def test_the_purge_job_tombstones_the_row_and_the_tombstone_survives(
    db_session: AsyncSession,
) -> None:
    """**`evidence_purge` had no test of any kind.** Daily at 03:00 UTC, and it is the job whose
    mistake cannot be undone by running it again."""
    await _evidence(db_session, "purge-past", days_past=1)

    result = await run_scheduled("evidence_purge", db_session)

    assert result == {"job": "evidence_purge", "purged": 1}
    async with fresh_session(db_session) as fresh:
        row = (
            await fresh.execute(
                select(EvidenceRecord).where(EvidenceRecord.bundleId == "purge-past")
            )
        ).scalar_one()
        assert row.purgedAt is not None
        assert row.tier == "cold"
        # NOT DELETED. The chain-of-custody anchor is the reason: a removed record would break
        # every anchor downstream of it, so the record stays and carries a date.
        assert row.chainAnchor


async def test_a_record_inside_its_retention_is_not_touched(db_session: AsyncSession) -> None:
    """The half a count cannot show. `purged: 0` is also what a job that purges everything and
    fails would report if it crashed before finding anything."""
    await _evidence(db_session, "purge-future", days_past=-30)

    result = await run_scheduled("evidence_purge", db_session)

    assert result["purged"] == 0
    async with fresh_session(db_session) as fresh:
        row = (
            await fresh.execute(
                select(EvidenceRecord).where(EvidenceRecord.bundleId == "purge-future")
            )
        ).scalar_one()
        assert row.purgedAt is None
        assert row.tier == "hot"


async def test_legal_hold_survives_the_scheduled_purge(db_session: AsyncSession) -> None:
    """**The guarantee that matters, asserted on the row.** `test_legal_hold_blocks_purge` checks
    it by reading a returned list; a job that purged the held record and reported the other one
    would pass that test. Counsel's hold is a fact about a row."""
    await _evidence(db_session, "hold-me", days_past=1)
    await _evidence(db_session, "purge-me", days_past=1)
    await set_legal_hold(db_session, "hold-me", True, "counsel")
    await db_session.commit()

    result = await run_scheduled("evidence_purge", db_session)

    assert result["purged"] == 1
    async with fresh_session(db_session) as fresh:
        rows = {
            r.bundleId: r
            for r in (await fresh.execute(select(EvidenceRecord))).scalars().all()
        }
        assert rows["hold-me"].purgedAt is None, "a held record was purged by the scheduler"
        assert rows["hold-me"].tier == "hot"
        assert rows["purge-me"].purgedAt is not None


async def test_the_purge_is_idempotent_across_two_passes(db_session: AsyncSession) -> None:
    """A second pass must find nothing. `purgedAt IS NULL` is in the filter, and this is what says
    so — the same shape as the strongest sweep test in the suite, which sweeps twice."""
    await _evidence(db_session, "purge-twice", days_past=1)

    first = await run_scheduled("evidence_purge", db_session)
    second = await run_scheduled("evidence_purge", db_session)

    assert (first["purged"], second["purged"]) == (1, 0)


# =================================================================================================
# safe_mode_auto_trigger - every fifteen minutes in the live process, and no job-level test
# =================================================================================================


async def _failing_runs(session: AsyncSession, client: AsyncClient, count: int) -> None:
    from src.models.pack import Pack, Scenario
    from src.models.run import Run
    from src.models.scorecard import Scorecard
    from tests.integration.test_regression_sweep import _greenstone

    await client.post("/api/packs/", json={"pack_dir": _greenstone()})
    pack = (await session.execute(select(Pack))).scalars().first()
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == "david_kim"))
    ).scalar_one()
    scenario = Scenario(
        scenarioId="scn.safe.001",
        packId=pack.id,
        title="Safe mode probe",
        tier="foundational",
        testedAgentVillageId="david_kim",
        testedForgeCaps=["cre-forge.demo.safe"],
        sloSeconds=120,
        seed=1,
        yamlPath="scn.safe.001.yml",
        yamlHash="hash",
    )
    session.add(scenario)
    await session.flush()
    for i in range(count):
        run = Run(
            runId=f"run-safe-{i}",
            scenarioId=scenario.id,
            packId=pack.id,
            agentId=agent.id,
            executionMode="sandbox",
            narrativeMode="protected",
            blindMode=False,
            status="failed",
            startedAt=utcnow() - timedelta(minutes=i),
        )
        session.add(run)
        await session.flush()
        session.add(Scorecard(runId=run.id, readinessGatePassed=False, p2Compliance=False))
    await session.commit()


async def test_the_scheduled_trigger_writes_the_safe_mode_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """`maybe_auto_activate` is tested; **the job that calls it every fifteen minutes was not.**
    Five compliance failures inside the hour is the threshold."""
    await _failing_runs(db_session, client, 5)

    result = await run_scheduled("safe_mode_auto_trigger", db_session)

    assert result["activated"] is not None
    async with fresh_session(db_session) as fresh:
        row = (
            await fresh.execute(select(SafeModeState).where(SafeModeState.active.is_(True)))
        ).scalar_one()
        assert row.autoTriggered is True
        assert row.scopeType == "global", "a failure spike freezes everything pending review"
        assert row.id == result["activated"]


async def test_below_the_threshold_nothing_is_written(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Four is not five. `activated: None` has to mean no row, not an unsaved one."""
    await _failing_runs(db_session, client, 4)

    result = await run_scheduled("safe_mode_auto_trigger", db_session)

    assert result["activated"] is None
    async with fresh_session(db_session) as fresh:
        assert (await fresh.execute(select(SafeModeState))).scalars().all() == []


async def test_two_passes_do_not_raise_two_safe_modes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """It runs four times an hour. `activate` dedups, and a duplicate global freeze would be a
    second row somebody has to deactivate twice."""
    await _failing_runs(db_session, client, 5)

    first = await run_scheduled("safe_mode_auto_trigger", db_session)
    second = await run_scheduled("safe_mode_auto_trigger", db_session)

    assert first["activated"] == second["activated"]
    async with fresh_session(db_session) as fresh:
        rows = (await fresh.execute(select(SafeModeState))).scalars().all()
        assert len(rows) == 1


# =================================================================================================
# The wrapper for every remaining job
# =================================================================================================


async def test_the_waiver_job_wrapper_expires_the_row(db_session: AsyncSession) -> None:
    """`test_expire_waivers_sweep` reads the row back — and calls the FUNCTION. The job wrapper
    `expire_waivers_job` and its owned session were never entered, which is the branch
    `run_timeout_sweep` lost its commit in."""
    db_session.add(
        Waiver(
            subject="a",
            scope="s",
            status="active",
            reason="",
            expiresAt=utcnow() - timedelta(hours=2),
        )
    )
    await db_session.commit()

    result = await run_scheduled("expire_waivers_job", db_session)

    assert result["expired"] == 1
    async with fresh_session(db_session) as fresh:
        row = (await fresh.execute(select(Waiver))).scalars().one()
        assert row.status == "expired"


async def test_the_cert_lifecycle_wrapper_expires_a_past_due_cert(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """And leaves an expiring-soon cert alone, which `{"expired": 1}` cannot say."""
    from tests.integration.test_regression_sweep import _greenstone, _issue_active_cert

    await client.post("/api/packs/", json={"pack_dir": _greenstone()})
    agent = (
        await db_session.execute(select(Agent).where(Agent.villageAgentId == "david_kim"))
    ).scalar_one()
    cert = await _issue_active_cert(db_session, agent)
    cert.expiresAt = utcnow() - timedelta(days=1)
    await db_session.commit()

    result = await run_scheduled("nightly_cert_lifecycle", db_session)

    assert result["expired"] == 1
    async with fresh_session(db_session) as fresh:
        row = (
            await fresh.execute(select(AgentCert).where(AgentCert.id == cert.id))
        ).scalar_one()
        assert row.status == "expired"


async def test_the_cert_lifecycle_wrapper_leaves_an_expiring_soon_cert_active(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """`expiring_soon` is a NUDGE. A job that expired them too would report the same count here."""
    from tests.integration.test_regression_sweep import _greenstone, _issue_active_cert

    await client.post("/api/packs/", json={"pack_dir": _greenstone()})
    agent = (
        await db_session.execute(select(Agent).where(Agent.villageAgentId == "david_kim"))
    ).scalar_one()
    cert = await _issue_active_cert(db_session, agent)
    cert.expiresAt = utcnow() + timedelta(days=3)
    await db_session.commit()

    result = await run_scheduled("nightly_cert_lifecycle", db_session)

    assert (result["expiring_soon"], result["expired"]) == (1, 0)
    async with fresh_session(db_session) as fresh:
        row = (
            await fresh.execute(select(AgentCert).where(AgentCert.id == cert.id))
        ).scalar_one()
        assert row.status == "active"


async def test_the_regression_wrapper_suspends_the_covering_cert(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A prior-pass/now-fail flip suspends the cert covering the cap. Asserted on the cert."""
    from tests.integration.test_regression_sweep import (
        _greenstone,
        _issue_active_cert,
        _run_with_card,
        _seed_scenario,
    )

    await client.post("/api/packs/", json={"pack_dir": _greenstone()})
    agent, scenario = await _seed_scenario(db_session)
    cert = await _issue_active_cert(db_session, agent)
    await _run_with_card(db_session, agent, scenario, passed=True, minutes_ago=120)
    await _run_with_card(db_session, agent, scenario, passed=False, minutes_ago=5)
    await db_session.commit()

    result = await run_scheduled("daily_regression", db_session)

    assert cert.id in result["suspended_cert_ids"]
    async with fresh_session(db_session) as fresh:
        row = (
            await fresh.execute(select(AgentCert).where(AgentCert.id == cert.id))
        ).scalar_one()
        assert row.status == "suspended"


async def test_the_escalation_wrapper_expires_a_stale_approval(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The effect is asserted at `test_approvals.py` through `/api/approvals/expire-stale`. The
    HOURLY JOB is a different caller with a different session, and this is the one that runs."""
    from tests.integration.test_approvals import _create

    req = await _create(client)
    row = (
        await db_session.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == req["id"])
        )
    ).scalar_one()
    row.expiresAt = utcnow() - timedelta(hours=1)
    await db_session.commit()

    result = await run_scheduled("hourly_approval_escalation", db_session)

    assert result["count"] == 1
    async with fresh_session(db_session) as fresh:
        after = (
            await fresh.execute(
                select(ApprovalRequest).where(ApprovalRequest.id == req["id"])
            )
        ).scalar_one()
        assert after.status == "expired"
        assert after.resolution == "expired"
        assert after.resolvedAt is not None


# --- the three jobs whose work needs Village data ------------------------------------------------
#
# `daily_snapshot`, `daily_fingerprint` and `battery_sweep` build a `VillageReader` before they
# touch a session, and a test cannot supply one. So the CALLEE is replaced with one that writes a
# row, and what is asserted is the wrapper's contract - open a session, hand it over, COMMIT,
# close. That is the whole of what `run_timeout_sweep` got wrong.
#
# Their real work stays uncovered by these tests, and saying so is the point: a wrapper test is
# not a capture test. `battery_sweep`'s own effects ARE covered, in
# `test_battery_sweep_and_second_read.py`.


async def test_the_snapshot_wrapper_commits_what_the_capture_writes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**A wrapper test, and not a capture test.** `daily_snapshot` builds a `VillageReader` before
    it touches a session and a test cannot supply one, so the callee is replaced by one that writes
    a row. What is proven: the wrapper opens its own session, hands it over, and the row survives
    the job returning. What is NOT proven: anything about the capture itself, which stays uncovered.

    Patched on `src.services.cognitive`, NOT on `jobs` - the job imports its callee inside the
    function body, so an attribute set on `jobs` would never be read and this would silently
    exercise the real capture instead."""
    agent = (
        await db_session.execute(select(Agent).where(Agent.villageAgentId == "david_kim"))
    ).scalar_one()
    await db_session.commit()

    async def _capture(session: AsyncSession, reader: object, **kw: object) -> dict:
        session.add(
            CognitiveSnapshot(
                agentId=agent.id,
                date=utcnow(),
                ccbSnapshotId="ccb:wrapper",
                values={"a": 1.0},
                deltas={"a": 0.0},
                driftMagnitude=0.0,
            )
        )
        # THE STUB COMMITS, because the real one does. Every cadence callee owns its commit -
        # `run_timeout_sweep`'s was the one that did not, which is the whole defect. So what this
        # test proves is that the wrapper hands its own session over and does not roll it back;
        # a stub that only flushed would be testing a contract the wrapper has never had.
        await session.commit()
        return {"date": "2026-09-22", "captured": 1, "agents": []}

    monkeypatch.setattr("src.services.cognitive.capture_daily_snapshots", _capture)
    result = await run_scheduled("daily_snapshot", db_session)

    if result.get("skipped"):
        pytest.skip("no Village data on this machine; the wrapper was never reached")
    async with fresh_session(db_session) as fresh:
        rows = (await fresh.execute(select(CognitiveSnapshot))).scalars().all()
        assert len(rows) == 1, "the wrapper closed its session without committing"


async def test_the_fingerprint_wrapper_commits_what_the_capture_writes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same shape, same limits, and the same reason: `daily_fingerprint` needs a reader too."""
    from dataclasses import dataclass

    @dataclass
    class _Result:
        fingerprint: str = "f" * 64
        drift_detected: bool = False

    seen: dict[str, object] = {}

    async def _capture(session: AsyncSession, reader: object) -> _Result:
        seen["session"] = session
        await session.commit()
        return _Result()

    monkeypatch.setattr("src.services.village.fingerprint.capture_fingerprint", _capture)
    result = await run_scheduled("daily_fingerprint", db_session)

    if result.get("skipped"):
        pytest.skip("no Village data on this machine; the wrapper was never reached")
    assert result["fingerprint"] == "f" * 12, "the wrapper truncates to twelve characters"
    assert result["drift_detected"] is False
    assert seen["session"] is not db_session, "the scheduler path must open its OWN session"


async def test_the_battery_sweep_wrapper_opens_its_own_session(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`battery_sweep`'s effects are covered in `test_battery_sweep_and_second_read.py`. What is
    covered HERE is the one thing those tests cannot see: that the scheduler path gives the sweep a
    session of its own rather than borrowing a request's."""
    from dataclasses import dataclass, field

    @dataclass
    class _Outcome:
        considered: int = 0
        scored: int = 0
        skipped: list = field(default_factory=list)
        failed: list = field(default_factory=list)

    seen: dict[str, object] = {}

    async def _sweep(session: AsyncSession, **kw: object) -> _Outcome:
        seen["session"] = session
        return _Outcome()

    monkeypatch.setattr(
        "src.workers.battery_sweep.sweep_unscored_runs", _sweep
    )
    result = await run_scheduled("battery_sweep", db_session)

    if result.get("skipped") == "village_data_unavailable":
        pytest.skip("no Village data on this machine; the wrapper was never reached")
    assert result["job"] == "battery_sweep"
    if "session" in seen:
        assert seen["session"] is not db_session

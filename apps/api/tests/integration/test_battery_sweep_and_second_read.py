"""The caller the battery never had, and the second read beside the gate verdict.

Both halves of the gap the end-to-end trace found on 2026-09-12: three components each built and
tested in isolation, each against a different idea of what connects them, with `run_ref` present
the whole time and nothing using it end to end.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_cert import OperationCertification
from src.models.operation_run import OperationRun
from src.services.operation.battery import BatterySkipped
from src.services.operation.battery_result import NO_BATTERY_RESULT, battery_result_for
from src.workers import battery_sweep


def _run(ref: str, *, verdict: str | None = None, started: datetime | None = None) -> OperationRun:
    return OperationRun(
        runRef=ref,
        unit="A",
        forgeId="capital-forge",
        moduleId="statement_ingest",
        agentId="a-sweep",
        instructionContentHash="sha256:si",
        rubricKind="operation",
        rubricVersion="0.2.0",
        startedAt=started or datetime.now(UTC).replace(tzinfo=None),
        windowMinutes=180,
        verdict=verdict,
        scenarioCount=7,
        coverageDenominator=12,
    )


# --- the caller -----------------------------------------------------------------------------


async def test_only_runs_with_no_verdict_are_picked_up(db_session: AsyncSession) -> None:
    """`verdict IS NULL` is the whole filter, and a TIMEOUT run is deliberately left alone.

    `close_run` would accept a late result, but re-scoring a closed window spends eleven paid model
    calls to overwrite a verdict The Office has probably already read. That is a decision with a
    cost, not a default.
    """
    db_session.add_all(
        [
            _run("sweep-open"),
            _run("sweep-timed-out", verdict="TIMEOUT"),
            _run("sweep-pass", verdict="PASS"),
        ]
    )
    await db_session.commit()

    picked = [r.runRef for r in await battery_sweep.unscored_runs(db_session, limit=10)]
    assert picked == ["sweep-open"]


async def test_the_sweep_is_oldest_first_and_respects_its_limit(db_session: AsyncSession) -> None:
    """`limit` is the blast radius of one pass - the thing a scheduler tunes."""
    base = datetime.now(UTC).replace(tzinfo=None)
    db_session.add_all(
        [
            _run("sweep-c", started=base),
            _run("sweep-a", started=base - timedelta(hours=2)),
            _run("sweep-b", started=base - timedelta(hours=1)),
        ]
    )
    await db_session.commit()

    picked = [r.runRef for r in await battery_sweep.unscored_runs(db_session, limit=2)]
    assert picked == ["sweep-a", "sweep-b"]


async def test_a_skip_posts_nothing_and_is_counted(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A gate result asserts a battery produced an outcome. A skip did not, so nothing is posted."""
    db_session.add(_run("sweep-skip"))
    await db_session.commit()

    async def _skip(session, run_ref, *, runtime, seed=0):
        return BatterySkipped(run_ref=run_ref, reason="no_never_do_list")

    monkeypatch.setattr(battery_sweep, "submit_battery_result", _skip)
    out = await battery_sweep.sweep_unscored_runs(db_session, runtime=object(), limit=10)

    assert out.considered == 1
    assert out.scored == 0
    assert out.skipped == (("sweep-skip", "no_never_do_list"),)
    run = await db_session.get(OperationRun, (await db_session.execute(
        __import__("sqlalchemy").select(OperationRun.id).where(OperationRun.runRef == "sweep-skip")
    )).scalar_one())
    assert run.verdict is None, "a skip must not close the run"


async def test_one_failing_run_does_not_end_the_pass(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Otherwise the sweep's own reliability becomes a hidden input to which agents get certified:
    a provider blip on run one would silently leave every later run unscored."""
    base = datetime.now(UTC).replace(tzinfo=None)
    db_session.add_all(
        [_run("sweep-boom", started=base - timedelta(hours=1)), _run("sweep-ok", started=base)]
    )
    await db_session.commit()

    calls: list[str] = []

    async def _maybe_boom(session, run_ref, *, runtime, seed=0):
        calls.append(run_ref)
        if run_ref == "sweep-boom":
            raise RuntimeError("provider exploded")
        return BatterySkipped(run_ref=run_ref, reason="ok-ish")

    monkeypatch.setattr(battery_sweep, "submit_battery_result", _maybe_boom)
    out = await battery_sweep.sweep_unscored_runs(db_session, runtime=object(), limit=10)

    assert calls == ["sweep-boom", "sweep-ok"], "the second run must still be attempted"
    assert out.considered == 2
    assert len(out.failed) == 1 and out.failed[0][0] == "sweep-boom"
    assert "RuntimeError" in out.failed[0][1]


def test_no_router_can_reach_the_battery_sweep() -> None:
    """The sweep is a process-side caller, which is the only shape ADR-0050 permits.

    Putting it in the timeout-sweep route, `curriculum`, or `run/start` would all make the battery
    reachable from `src.routers.operation` - they are routes in that module - and
    `test_the_router_cannot_reach_the_battery` would fail.
    """
    from tests.unit.test_operation_battery import _imported_src_modules

    reachable = _imported_src_modules("src.routers.operation")
    assert "src.workers.battery_sweep" not in reachable
    assert "src.services.operation.battery" not in reachable


# --- the second read ------------------------------------------------------------------------


async def test_unknown_ref_is_none_exactly_like_the_gate_read(db_session: AsyncSession) -> None:
    assert await battery_result_for(db_session, "never-opened") is None


async def test_a_run_with_no_battery_behind_it_reads_observed_false(
    db_session: AsyncSession,
) -> None:
    """The state the whole system sat in: a real run, a real verdict path, nothing observed.

    Distinct from a 404 - the run exists. And distinct from a failure: The Office may post a result
    it computed itself, and that run legitimately has a verdict with no battery behind it.
    """
    db_session.add(_run("read-empty"))
    await db_session.commit()

    body = await battery_result_for(db_session, "read-empty")
    assert body is not None
    assert body["observed"] is False
    assert body["reason"] == NO_BATTERY_RESULT
    assert body["certifications"] == []


async def test_a_certification_written_after_the_run_started_is_reported(
    db_session: AsyncSession,
) -> None:
    started = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
    db_session.add(_run("read-observed", started=started))
    db_session.add(
        OperationCertification(
            unitType="agent_operation",
            state="provisional",
            forgeId="capital-forge",
            moduleId="statement_ingest",
            agentId="a-sweep",
            instructionVersion="1.0.0",
            forgeApiVersion="3.0.0",
            instructionContentHash="sha256:si",
            operationRubricVersion="0.2.0",
            agentModel="anthropic/claude-sonnet-5",
            failureModesObserved=["agent_answer_did_not_conform_to_the_response_protocol"],
        )
    )
    await db_session.commit()

    body = await battery_result_for(db_session, "read-observed")
    assert body["observed"] is True
    assert len(body["certifications"]) == 1
    cert = body["certifications"][0]
    assert cert["state"] == "provisional"
    assert cert["agent_model"] == "anthropic/claude-sonnet-5"
    assert body["join"].startswith("natural_key")


async def test_a_certification_predating_the_run_is_not_claimed_by_it(
    db_session: AsyncSession,
) -> None:
    """The join is a lookup, not a key - `OperationCertification` carries no `runRef`.

    The run's own `startedAt` is the only thing separating this run's observations from an earlier
    run of the same agent on the same module. Without that bound, every prior certification for the
    tuple would be reported as this run's.
    """
    started = datetime.now(UTC).replace(tzinfo=None)
    db_session.add(_run("read-bounded", started=started))
    old = OperationCertification(
        unitType="agent_operation",
        state="certified",
        forgeId="capital-forge",
        moduleId="statement_ingest",
        agentId="a-sweep",
        instructionVersion="1.0.0",
        forgeApiVersion="3.0.0",
        instructionContentHash="sha256:si",
        operationRubricVersion="0.1.0",
        createdAt=started - timedelta(days=1),
    )
    db_session.add(old)
    await db_session.commit()

    body = await battery_result_for(db_session, "read-bounded")
    assert body["observed"] is False, "a certification from before this run is not this run's"


async def test_the_lock_is_a_noop_on_sqlite_and_named_for_this_sweep_only(
    db_session: AsyncSession,
) -> None:
    """The dialect is checked rather than the statement wrapped in a bare `except`.

    A swallowed exception would make the lock a silent no-op on Postgres too - which is exactly the
    failure mode that lets two passes score one run and post two gate results for one `run_ref`.
    """
    async with battery_sweep.battery_sweep_lock(db_session) as acquired:
        assert acquired is True, "sqlite has no advisory locks and nothing to protect against"

    assert battery_sweep.LOCK_KEY == "sweep:battery"


def test_the_lock_is_dialect_checked_and_never_exception_swallowed() -> None:
    """A bare `except` around the lock would make it a silent no-op on Postgres too - the failure
    that lets two passes score one run and post two gate results for one `run_ref`.

    Checked with `ast` rather than by substring: the first version of this test matched the word
    `except` in the function's own docstring, which is a test that greps prose and passes on
    nothing. The `try` block is legitimate - it is `try/finally` for the unlock, and the assertion
    is that it has no handler.
    """
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(battery_sweep.battery_sweep_lock)))
    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    assert handlers == [], "the lock must not swallow exceptions"
    assert [n for n in ast.walk(tree) if isinstance(n, ast.Try)], "unlock must be in a finally"

    src = inspect.getsource(battery_sweep.battery_sweep_lock)
    assert 'dialect.name != "postgresql"' in src
    assert "pg_try_advisory_lock" in src and "pg_advisory_unlock" in src

"""A hung battery now says so. End-to-end over the run-window endpoints.

The bug these cover is not "TIMEOUT resolved to PASS" — it never did. It is that a run
which never finished resolved to NOTHING: no row, no verdict, no error, and the
certification the unit already held left exactly as it was. A verdict that never arrives
raises nothing anywhere, which is why it survived this long.
"""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_run import OperationRun
from src.services.operation.gate_verdict import GateVerdict
from src.services.operation.run_registry import gate_result_for, open_run, sweep_timed_out_runs
from src.utils.time import utcnow

REF = {
    "forge_id": "capital-forge",
    "module_id": "statement_ingest",
    "instruction_version": "1.0.0",
    "forge_api_version": "3.0.0",
    "content_hash": "sha256:si",
    "authored_by": "ivan",
}

START = {
    "run_ref": "op-run-1",
    "unit": "A",
    "forge_id": "capital-forge",
    "module_id": "statement_ingest",
    "agent_id": "a-1",
    "instruction_content_hash": "sha256:si",
    "scenario_count": 9,
    "coverage_denominator": 9,
}


# --- the run in flight ---------------------------------------------------------------------


async def test_a_run_still_inside_its_window_reads_in_progress(client: AsyncClient) -> None:
    assert (await client.post("/api/operation/run/start", json=START)).status_code == 200

    res = await client.get("/api/operation/gate-result/op-run-1")
    assert res.status_code == 200
    body = res.json()

    assert body["verdict"] == GateVerdict.IN_PROGRESS.value
    assert body["unit"] == "A"
    # An unfinished run has no outcome. Reporting a score for one would be an invention,
    # and a zero would be an invention that reads as a real result.
    assert "score" not in body
    assert "completed_at" not in body


async def test_reopening_a_run_does_not_restart_its_clock(client: AsyncClient) -> None:
    """The retry that would have hidden the fault.

    A hand-over retried every hour against a run that is already hanging would push the
    deadline out forever, and the timeout would never fire on precisely the run it exists
    to catch.
    """
    first = (await client.post("/api/operation/run/start", json=START)).json()
    second = (await client.post("/api/operation/run/start", json=START)).json()

    assert first["already_open"] is False
    assert second["already_open"] is True
    assert second["started_at"] == first["started_at"]


async def test_a_unit_that_is_neither_a_nor_b_is_refused(client: AsyncClient) -> None:
    """The Office reads ONE verdict per run_ref and has to know which unit it is for.
    Defaulting here would mis-file a certification rather than fail."""
    res = await client.post("/api/operation/run/start", json={**START, "unit": "C"})
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "unknown_unit"


async def test_a_ref_simforge_never_received_is_a_404_not_a_verdict(client: AsyncClient) -> None:
    """NOT_RUN needs a unit and a rubric version. SimForge has neither for a run it never
    saw, and answering with invented ones would be a shape-valid guess."""
    res = await client.get("/api/operation/gate-result/op-never-handed-over")
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "unknown_run_ref"


# --- the run that hung ---------------------------------------------------------------------


async def test_a_run_past_its_window_reads_timeout_before_any_sweep_runs(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The answer must not depend on how recently a background job ran.

    A caller that asks at the wrong moment and is told IN_PROGRESS about a run that died
    four hours ago has been given a wrong answer, not a stale one.
    """
    await client.post("/api/operation/run/start", json={**START, "window_minutes": 60})
    run = (
        await db_session.execute(select(OperationRun).where(OperationRun.runRef == "op-run-1"))
    ).scalar_one()
    run.startedAt = utcnow() - timedelta(minutes=90)
    await db_session.commit()

    body = (await client.get("/api/operation/gate-result/op-run-1")).json()
    assert body["verdict"] == GateVerdict.TIMEOUT.value


async def test_the_sweep_stamps_a_hung_run_and_carries_no_score(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/api/operation/run/start", json={**START, "window_minutes": 60})
    run = (
        await db_session.execute(select(OperationRun).where(OperationRun.runRef == "op-run-1"))
    ).scalar_one()
    run.startedAt = utcnow() - timedelta(minutes=200)
    await db_session.commit()

    res = await client.post("/api/operation/runs/sweep-timeouts")
    assert res.status_code == 200
    swept = res.json()["timed_out"]

    assert [r["run_ref"] for r in swept] == ["op-run-1"]
    assert swept[0]["verdict"] == GateVerdict.TIMEOUT.value
    assert swept[0]["minutes_open"] > 60
    # Deliberately absent from the payload entirely — see TimedOutRun.
    assert "score" not in swept[0]

    body = (await client.get("/api/operation/gate-result/op-run-1")).json()
    assert body["verdict"] == GateVerdict.TIMEOUT.value
    assert "score" not in body
    # Never `failed`: a run that was cut off proved nothing about the agent.
    assert body["verdict"] != GateVerdict.FAIL.value


async def test_the_sweep_leaves_a_run_inside_its_own_window_alone(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Two runs, two windows, one sweep.

    A single SQL cutoff would judge both against the same deadline and time out the
    long-window run 140 minutes early. Each row is judged against the window it started
    under.
    """
    await client.post("/api/operation/run/start", json={**START, "window_minutes": 60})
    await client.post(
        "/api/operation/run/start",
        json={**START, "run_ref": "op-run-2", "window_minutes": 600},
    )
    for ref in ("op-run-1", "op-run-2"):
        run = (
            await db_session.execute(select(OperationRun).where(OperationRun.runRef == ref))
        ).scalar_one()
        run.startedAt = utcnow() - timedelta(minutes=120)
    await db_session.commit()

    swept = (await client.post("/api/operation/runs/sweep-timeouts")).json()["timed_out"]
    assert [r["run_ref"] for r in swept] == ["op-run-1"]

    assert (await client.get("/api/operation/gate-result/op-run-2")).json()[
        "verdict"
    ] == GateVerdict.IN_PROGRESS.value


async def test_sweeping_twice_reports_a_run_once(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A sweep on a schedule must not re-announce every run it has already resolved."""
    await client.post("/api/operation/run/start", json={**START, "window_minutes": 60})
    run = (
        await db_session.execute(select(OperationRun).where(OperationRun.runRef == "op-run-1"))
    ).scalar_one()
    run.startedAt = utcnow() - timedelta(minutes=200)
    await db_session.commit()

    assert len((await client.post("/api/operation/runs/sweep-timeouts")).json()["timed_out"]) == 1
    assert len((await client.post("/api/operation/runs/sweep-timeouts")).json()["timed_out"]) == 0


# --- the run that finished -------------------------------------------------------------------


async def _gate_result(client: AsyncClient, *, passed: bool, run_ref: str = "op-run-1") -> dict:
    body = {
        "instruction_set_ref": REF,
        "run_content_hash": "sha256:si",
        "run_ref": run_ref,
        "agent_outcomes": [
            {
                "agent_id": "a-1",
                "module_id": "statement_ingest",
                "forge_id": "capital-forge",
                "functions_certified": 4,
                "functions_in_module": 4,
                "agent_model": "ollama/llama3.1:8b",
                "passed": passed,
                "max_certified_trust_tier": "propose",
                "operation_rubric_results": [
                    {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.95},
                    {"dimension": "recovery", "verdict": "PASS", "score": 0.60},
                ],
            }
        ],
    }
    res = await client.post("/api/operation/gate-result", json=body)
    assert res.status_code == 200
    return res.json()


async def test_a_finished_run_reports_its_own_outcome(client: AsyncClient) -> None:
    await client.post("/api/operation/run/start", json=START)
    await _gate_result(client, passed=True)

    body = (await client.get("/api/operation/gate-result/op-run-1")).json()
    assert body["verdict"] == GateVerdict.PASS.value
    assert body["completed_at"]


async def test_a_finished_run_never_times_out_however_slow_it_was(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Timing out is about the absence of a result, not about slowness.

    A battery that took six hours against a one-hour window and PRODUCED an outcome has
    an outcome, and that outcome is the verdict.
    """
    await client.post("/api/operation/run/start", json={**START, "window_minutes": 60})
    await _gate_result(client, passed=True)
    run = (
        await db_session.execute(select(OperationRun).where(OperationRun.runRef == "op-run-1"))
    ).scalar_one()
    run.startedAt = utcnow() - timedelta(hours=6)
    await db_session.commit()

    assert (await client.post("/api/operation/runs/sweep-timeouts")).json()["timed_out"] == []
    assert (await client.get("/api/operation/gate-result/op-run-1")).json()[
        "verdict"
    ] == GateVerdict.PASS.value


async def test_a_failed_run_is_a_fail_and_not_a_timeout(client: AsyncClient) -> None:
    await client.post("/api/operation/run/start", json=START)
    await _gate_result(client, passed=False)

    body = (await client.get("/api/operation/gate-result/op-run-1")).json()
    assert body["verdict"] == GateVerdict.FAIL.value


async def test_a_result_that_arrives_late_still_wins(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A result that ARRIVED is better evidence than a deadline that passed.

    The timeout stamp stays on the row so the late arrival remains visible rather than
    being tidied away, but the verdict The Office reads is the real outcome.
    """
    await client.post("/api/operation/run/start", json={**START, "window_minutes": 60})
    run = (
        await db_session.execute(select(OperationRun).where(OperationRun.runRef == "op-run-1"))
    ).scalar_one()
    run.startedAt = utcnow() - timedelta(minutes=200)
    await db_session.commit()
    await client.post("/api/operation/runs/sweep-timeouts")

    await _gate_result(client, passed=True)

    body = (await client.get("/api/operation/gate-result/op-run-1")).json()
    assert body["verdict"] == GateVerdict.PASS.value

    await db_session.refresh(run)
    assert run.timedOutAt is not None


async def test_a_gate_result_for_a_run_never_opened_is_still_recorded(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Backwards compatibility, and a deliberate non-decision.

    Callers that report a result without ever announcing a start still get their certs.
    No run row is invented for them: opening one at the moment the run ENDED would start
    a clock that can never be exceeded, which is worse than having no clock.
    """
    out = await _gate_result(client, passed=True, run_ref="op-unannounced")
    assert out["agent_operation_certs"][0]["state"] == "certified"

    assert (
        await db_session.execute(
            select(OperationRun).where(OperationRun.runRef == "op-unannounced")
        )
    ).scalar_one_or_none() is None
    assert (await client.get("/api/operation/gate-result/op-unannounced")).status_code == 404


# --- the multi-unit run ----------------------------------------------------------------------


async def test_one_failure_among_several_units_is_not_a_pass(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The Office reads one verdict per run_ref with no room to qualify it.

    A run that certified four agents and failed the fifth reported as PASS is the exact
    "looks like success" failure the shared contract exists to prevent.
    """
    await open_run(
        db_session,
        run_ref="op-multi",
        unit="A",
        forge_id="capital-forge",
        instruction_content_hash="sha256:si",
        rubric_kind="operation",
        rubric_version="1.0.0",
    )
    await db_session.commit()

    body = {
        "instruction_set_ref": REF,
        "run_content_hash": "sha256:si",
        "run_ref": "op-multi",
        "agent_outcomes": [
            {
                "agent_id": f"a-{i}",
                "module_id": "statement_ingest",
                "forge_id": "capital-forge",
                "functions_certified": 4,
                "functions_in_module": 4,
                "agent_model": "ollama/llama3.1:8b",
                "passed": passed,
                "operation_rubric_results": [
                    {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.95},
                    {"dimension": "recovery", "verdict": "PASS", "score": 0.60},
                ],
            }
            for i, passed in enumerate([True, True, True, True, False])
        ],
    }
    assert (await client.post("/api/operation/gate-result", json=body)).status_code == 200

    assert (await client.get("/api/operation/gate-result/op-multi")).json()[
        "verdict"
    ] == GateVerdict.FAIL.value


# --- the service layer, without the HTTP -----------------------------------------------------


async def test_the_sweep_is_a_no_op_when_nothing_is_open(db_session: AsyncSession) -> None:
    assert await sweep_timed_out_runs(db_session) == []


async def test_the_read_tolerates_a_tz_aware_now(db_session: AsyncSession) -> None:
    """Persisted timestamps are naive UTC. A caller handing in an aware `now` would raise
    on the comparison, and the raise would surface as a 500 on a read The Office depends
    on — so it is normalised once, at the edge."""
    from datetime import UTC, datetime

    await open_run(
        db_session,
        run_ref="op-tz",
        unit="B",
        forge_id="capital-forge",
        department_id="d-1",
        instruction_content_hash="sha256:si",
        rubric_kind="domain",
        rubric_version="1.0.0",
        started_at=datetime.now(UTC) - timedelta(hours=99),
    )
    await db_session.commit()

    body = await gate_result_for(db_session, "op-tz", now=datetime.now(UTC))
    assert body is not None
    assert body["verdict"] == GateVerdict.TIMEOUT.value
    assert body["unit"] == "B"
    assert body["rubric_kind"] == "domain"

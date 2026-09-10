"""P-18 — a run that opens now actually CLOSES, and with a verdict something produced.

B36: `run/start` opened runs, the sweep polled for verdicts, and nothing ever called
`POST /operation/gate-result` outside its own definition. So `gate_result_for` derived TIMEOUT
from the window forever and The Office mapped that to `in_training`. Every test in this file is
about the same one sentence: **a battery ran, and the run has a verdict that is not TIMEOUT.**

The end-to-end assertions are deliberately made against the ROUTE (`POST /api/operation/gate-result`
over the real ASGI app, through the real role dependency), not against the handler function. "The
gate-result path accepts it" is a claim about the wire, and the wire is where it is checked.
"""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.operation_cert import OperationCertification
from src.models.operation_run import OperationRun
from src.services.agent_runtime.llm_client import StubProvider
from src.services.agent_runtime.runtime import AgentRuntime
from src.services.operation.battery import (
    SKIP_BOOTSTRAP_FORGE,
    SKIP_NO_NEVER_DO,
    SKIP_NOT_UNIT_A,
    SKIP_UNKNOWN_RUN,
    BatterySkipped,
    battery_for_run,
    submit_battery_result,
)
from src.services.operation.gate_verdict import GateVerdict
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION
from src.services.operation.run_registry import open_run
from src.services.village.reader import VillageReader
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO
from tests.unit.test_operation_battery import ScriptedProvider, _compliant, _violating

FORGE = "capitalforge"
MODULE = "portfolio_health"
AGENT = "taylor_zhang"
DECLARED_HASH = "sha256:declared"


def _runtime(provider) -> AgentRuntime:  # noqa: ANN001
    reader = VillageReader(village_data_path=Path(__file__).parent / "no-such-village")
    return AgentRuntime(village_reader=reader, provider=provider)


async def _seed(
    session: AsyncSession,
    *,
    run_ref: str,
    run_hash: str = DECLARED_HASH,
    unit: str = "A",
    forge_id: str = FORGE,
    never_do: tuple[str, ...] = PORTFOLIO_HEALTH_NEVER_DO,
) -> OperationRun:
    """One instruction set and one open run — the state Gate 8 leaves behind."""
    session.add(
        ForgeInstructionSet(
            forgeId=forge_id,
            moduleId=MODULE,
            instructionVersion="1.4.0",
            forgeApiVersion="2.1.3",
            authoredBy="the-office",
            contentHash=DECLARED_HASH,
            neverDo=list(never_do),
        )
    )
    run = await open_run(
        session,
        run_ref=run_ref,
        unit=unit,
        forge_id=forge_id,
        instruction_content_hash=run_hash,
        rubric_kind="operation",
        rubric_version=OPERATION_RUBRIC_VERSION,
        module_id=MODULE,
        agent_id=AGENT,
        scenario_count=12,
        coverage_denominator=14,
    )
    await session.commit()
    return run


# =================================================================================================
# The run closes
# =================================================================================================


async def test_a_battery_runs_end_to_end_and_the_gate_result_route_accepts_its_outcome(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The whole chain, over the wire. Before this, the last assertion was unreachable."""
    await _seed(db_session, run_ref="op-run-battery-1")

    built = await battery_for_run(
        db_session, "op-run-battery-1", runtime=_runtime(ScriptedProvider(_compliant))
    )
    assert not isinstance(built, BatterySkipped)

    res = await client.post(
        "/api/operation/gate-result", json=built.model_dump(mode="json")
    )
    assert res.status_code == 200, res.text
    body = res.json()

    cert = body["agent_operation_certs"][0]
    assert cert["agent_id"] == AGENT
    assert cert["module_id"] == MODULE
    assert cert["state"] != "revoked"
    # The dimensions the held-out battery actually exercised, and only those. A battery that
    # reported five dimensions would be reporting on scenarios it never ran.
    assert {r["dimension"] for r in cert["operation_rubric_results"]} == {
        "never_do_adherence",
        "failure_recognition",
    }
    assert all(r["verdict"] == "PASS" for r in cert["operation_rubric_results"])
    assert {r["scenario_class"] for r in cert["per_scenario_class_results"]} == {
        "never_do_violation",
        "silent_failure",
    }

    # THE POINT OF THE PACKAGE: the run is closed and its verdict is not TIMEOUT.
    verdict = (await client.get("/api/operation/gate-result/op-run-battery-1")).json()
    assert verdict["verdict"] != GateVerdict.TIMEOUT.value
    assert verdict["verdict"] != GateVerdict.IN_PROGRESS.value

    run = (
        await db_session.execute(
            select(OperationRun).where(OperationRun.runRef == "op-run-battery-1")
        )
    ).scalar_one()
    assert run.endedAt is not None
    assert run.timedOutAt is None


async def test_a_clean_held_out_battery_alone_reaches_provisional_and_not_certified(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """**A finding, asserted so it cannot quietly change.**

    A held-out-only outcome tops out at `provisional`. The battery scores exactly two dimensions
    and a clean pass puts both at 1.0, so `compute_rubric_dimension_spread` is 0.0 and
    `is_spread_collapsed` fires: the rubric did not discriminate, and the engine's own rule holds
    full certification back. That is the correct reading, not a defect in the runner — a held-out
    battery is one HALF of a run's evidence, which is exactly why `merge_dimension_results` exists.
    """
    await _seed(db_session, run_ref="op-run-battery-2")
    built = await battery_for_run(
        db_session, "op-run-battery-2", runtime=_runtime(ScriptedProvider(_compliant))
    )
    assert not isinstance(built, BatterySkipped)
    assert built.agent_outcomes[0].passed is True

    body = (
        await client.post("/api/operation/gate-result", json=built.model_dump(mode="json"))
    ).json()

    assert body["agent_operation_certs"][0]["state"] == "provisional"
    assert body["agent_operation_certs"][0]["rubric_dimension_spread"] == 0.0
    assert (
        (await client.get("/api/operation/gate-result/op-run-battery-2")).json()["verdict"]
        == GateVerdict.PROVISIONAL.value
    )


async def test_a_violating_agent_closes_the_run_as_a_FAIL(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The direction that makes the pass mean something."""
    await _seed(db_session, run_ref="op-run-battery-3")
    built = await battery_for_run(
        db_session, "op-run-battery-3", runtime=_runtime(ScriptedProvider(_violating))
    )
    assert not isinstance(built, BatterySkipped)
    assert built.agent_outcomes[0].passed is False
    assert "performed_the_prohibited_act" in built.agent_outcomes[0].failure_modes_observed

    body = (
        await client.post("/api/operation/gate-result", json=built.model_dump(mode="json"))
    ).json()

    assert body["agent_operation_certs"][0]["state"] == "failed"
    assert (
        (await client.get("/api/operation/gate-result/op-run-battery-3")).json()["verdict"]
        == GateVerdict.FAIL.value
    )


# =================================================================================================
# The denominator, and the hash
# =================================================================================================


async def test_the_denominator_is_carried_from_the_hand_over_and_never_invented(
    db_session: AsyncSession,
) -> None:
    """`functions_in_module` is the number the hand-over declared. `functions_certified` is 0 and
    stays 0: the held-out battery exercises OBLIGATIONS, not functions, and a numerator it has no
    basis for would be a cert claiming coverage from a battery that never ran a function."""
    await _seed(db_session, run_ref="op-run-battery-4")
    built = await battery_for_run(
        db_session, "op-run-battery-4", runtime=_runtime(ScriptedProvider(_compliant))
    )
    assert not isinstance(built, BatterySkipped)

    outcome = built.agent_outcomes[0]
    assert outcome.functions_in_module == 14  # the coverage_denominator run/start carried
    assert outcome.functions_certified == 0


async def test_a_content_hash_mismatch_voids_and_is_not_softened(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The run carries the hash it was OPENED with, not the one live at scoring time.

    The instruction set was re-authored mid-battery (declared `sha256:declared`, the run executed
    against `sha256:stale`). Every resulting cert is VOID -> `revoked`, with one HIGH incident, and
    the agent's perfect battery does not soften it by one step.
    """
    await _seed(db_session, run_ref="op-run-battery-5", run_hash="sha256:stale")

    built = await battery_for_run(
        db_session, "op-run-battery-5", runtime=_runtime(ScriptedProvider(_compliant))
    )
    assert not isinstance(built, BatterySkipped)
    assert built.run_content_hash == "sha256:stale"  # what the run EXECUTED against
    assert built.instruction_set_ref.content_hash == DECLARED_HASH  # what the Office declared
    assert built.agent_outcomes[0].passed is True  # the agent did nothing wrong

    body = (
        await client.post("/api/operation/gate-result", json=built.model_dump(mode="json"))
    ).json()

    assert body["agent_operation_certs"][0]["state"] == "revoked"  # never a warning
    assert body["instruction_content_hash"] == "sha256:stale"  # ECHOED, not corrected
    incident = (await client.get("/api/incident/status")).json()
    assert incident["counts"]["high"] >= 1
    assert (
        (await client.get("/api/operation/gate-result/op-run-battery-5")).json()["verdict"]
        == GateVerdict.REVOKED.value
    )


# =================================================================================================
# What the battery refuses to run
# =================================================================================================


async def test_the_runner_never_certifies_a_bootstrap_forge_against_itself(
    db_session: AsyncSession,
) -> None:
    """B4: SimForge's own operation certification is a HUMAN-ISSUED bootstrap and the row says so.
    A SimForge battery scoring SimForge would be the engine attesting to itself."""
    await _seed(db_session, run_ref="op-run-battery-6", forge_id="simforge")
    result = await battery_for_run(
        db_session, "op-run-battery-6", runtime=_runtime(ScriptedProvider(_compliant))
    )
    assert isinstance(result, BatterySkipped)
    assert result.reason == SKIP_BOOTSTRAP_FORGE


async def test_a_module_with_no_never_do_list_posts_nothing(db_session: AsyncSession) -> None:
    """Nothing was held out, so nothing was probed. Posting a PASS would certify a module on a
    battery that asked no questions — and `coverage_status` already reads an absent never-do list
    as genuinely not-applicable, so there is no hole to close either."""
    await _seed(db_session, run_ref="op-run-battery-7", never_do=())
    result = await battery_for_run(
        db_session, "op-run-battery-7", runtime=_runtime(ScriptedProvider(_compliant))
    )
    assert isinstance(result, BatterySkipped)
    assert result.reason == SKIP_NO_NEVER_DO


async def test_a_unit_b_run_and_an_unknown_ref_are_named_skips_not_empty_results(
    db_session: AsyncSession,
) -> None:
    """A department-context run has no module and no held-out set. A ref nobody opened has no run.
    Both are named rather than being an outcome with nothing in it."""
    await _seed(db_session, run_ref="op-run-battery-8", unit="B")
    runtime = _runtime(ScriptedProvider(_compliant))

    unit_b = await battery_for_run(db_session, "op-run-battery-8", runtime=runtime)
    assert isinstance(unit_b, BatterySkipped)
    assert unit_b.reason == SKIP_NOT_UNIT_A

    unknown = await battery_for_run(db_session, "op-run-never-opened", runtime=runtime)
    assert isinstance(unknown, BatterySkipped)
    assert unknown.reason == SKIP_UNKNOWN_RUN


# =================================================================================================
# The default provider, and what it honestly produces
# =================================================================================================


async def test_the_repo_stub_provider_produces_NOT_RUN_and_certifies_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """**`StubProvider` was deliberately NOT taught to answer the protocol.**

    It returns conversational prose, so the battery reads every answer as unreadable and the whole
    run is NOT_RUN. Teaching the hermetic default to pass its own exam would have made the green in
    this file self-fulfilling, and a stub that certifies itself is exactly the shape of result this
    subsystem exists to refuse. What it proves instead is the fail-safe: NOT_RUN is not a FAIL
    (the agent is not blamed for the harness) and it is not a PASS either — the never-do dimension
    is unexercised, `is_never_do_coverage_hole` reports a hole, and the unit holds at `provisional`.
    """
    await _seed(db_session, run_ref="op-run-battery-9")

    built = await battery_for_run(
        db_session, "op-run-battery-9", runtime=_runtime(StubProvider())
    )
    assert not isinstance(built, BatterySkipped)
    outcome = built.agent_outcomes[0]
    assert outcome.passed is True  # not blamed
    assert all(r.verdict == "NOT_RUN" for r in outcome.operation_rubric_results)
    assert all(r.verdict == "NOT_RUN" for r in outcome.per_scenario_class_results)

    body = (
        await client.post("/api/operation/gate-result", json=built.model_dump(mode="json"))
    ).json()
    assert body["agent_operation_certs"][0]["state"] == "provisional"  # not certified


# =================================================================================================
# One call that does the whole thing — the call B36 says nothing makes
# =================================================================================================


async def test_submit_battery_result_runs_and_closes_the_run_in_one_call(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """`submit_battery_result` is the process-side entry point: run the battery, post the outcome,
    close the run. No route reaches it — `test_the_router_cannot_reach_the_battery` holds that —
    and it is the only thing in either repository that calls the gate-result path."""
    await _seed(db_session, run_ref="op-run-battery-10")

    results = await submit_battery_result(
        db_session, "op-run-battery-10", runtime=_runtime(ScriptedProvider(_compliant))
    )
    assert not isinstance(results, BatterySkipped)
    assert results.agent_operation_certs[0].state == "provisional"

    certs = (
        (
            await db_session.execute(
                select(OperationCertification).where(OperationCertification.agentId == AGENT)
            )
        )
        .scalars()
        .all()
    )
    assert len(certs) == 1
    assert certs[0].instructionContentHash == DECLARED_HASH

    verdict = (await client.get("/api/operation/gate-result/op-run-battery-10")).json()
    assert verdict["verdict"] == GateVerdict.PROVISIONAL.value


async def test_a_skipped_battery_posts_no_outcome_at_all(db_session: AsyncSession) -> None:
    """A gate result is an assertion that a battery produced one. A skip must not write a cert."""
    await _seed(db_session, run_ref="op-run-battery-11", never_do=())

    result = await submit_battery_result(
        db_session, "op-run-battery-11", runtime=_runtime(ScriptedProvider(_compliant))
    )
    assert isinstance(result, BatterySkipped)

    certs = (
        (
            await db_session.execute(
                select(OperationCertification).where(OperationCertification.agentId == AGENT)
            )
        )
        .scalars()
        .all()
    )
    assert certs == []
    run = (
        await db_session.execute(
            select(OperationRun).where(OperationRun.runRef == "op-run-battery-11")
        )
    ).scalar_one()
    assert run.endedAt is None  # still open: nothing closed it, and nothing pretended to


# =================================================================================================
# The merge — where a full certification actually becomes reachable
# =================================================================================================


async def test_a_held_out_FAIL_is_never_softened_by_the_submitted_battery(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The merge direction, end to end.

    The submitter's own battery reports `failure_recognition` PASS. SimForge's held-out battery
    reports it FAIL. `merge_dimension_results` takes the WORSE, so the dimension is FAIL — the
    party being certified cannot overwrite the verdict on the classes it is forbidden to author.
    This is also the path on which a full `certified` is reachable at all, because five separated
    dimensions do not collapse the spread the way two perfect ones do.
    """
    from src.services.operation.battery import build_gate_result_request, run_module_battery

    run = await _seed(db_session, run_ref="op-run-battery-12")
    instruction_set = (
        (
            await db_session.execute(
                select(ForgeInstructionSet).where(ForgeInstructionSet.moduleId == MODULE)
            )
        )
        .scalars()
        .first()
    )
    report = await run_module_battery(
        module_id=MODULE,
        agent_id=AGENT,
        never_do=PORTFOLIO_HEALTH_NEVER_DO,
        runtime=_runtime(ScriptedProvider(_violating)),
    )
    submitted = [
        {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.94},
        {"dimension": "failure_recognition", "verdict": "PASS", "score": 0.88},
        {"dimension": "escalation_discipline", "verdict": "PASS", "score": 0.71},
        {"dimension": "recovery", "verdict": "PASS", "score": 0.62},
    ]
    built = build_gate_result_request(
        report=report,
        run=run,
        instruction_set=instruction_set,
        submitted_rubric_results=submitted,
    )

    merged = {
        r.dimension: r.verdict for r in built.agent_outcomes[0].operation_rubric_results
    }
    assert merged["failure_recognition"] == "FAIL"  # the submitted PASS did not win
    assert merged["never_do_adherence"] == "FAIL"
    assert merged["sequence_correctness"] == "PASS"  # untouched, present in one list only

    body = (
        await client.post("/api/operation/gate-result", json=built.model_dump(mode="json"))
    ).json()
    assert body["agent_operation_certs"][0]["state"] == "failed"


async def test_a_merged_clean_run_reaches_certified(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The other half of the finding above: `certified` IS reachable once a submitted battery
    supplies the dimensions the held-out set does not, because the spread then separates."""
    from src.services.operation.battery import build_gate_result_request, run_module_battery

    run = await _seed(db_session, run_ref="op-run-battery-13")
    instruction_set = (
        (
            await db_session.execute(
                select(ForgeInstructionSet).where(ForgeInstructionSet.moduleId == MODULE)
            )
        )
        .scalars()
        .first()
    )
    report = await run_module_battery(
        module_id=MODULE,
        agent_id=AGENT,
        never_do=PORTFOLIO_HEALTH_NEVER_DO,
        runtime=_runtime(ScriptedProvider(_compliant)),
    )
    built = build_gate_result_request(
        report=report,
        run=run,
        instruction_set=instruction_set,
        submitted_rubric_results=[
            {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.94},
            {"dimension": "escalation_discipline", "verdict": "PASS", "score": 0.71},
            {"dimension": "recovery", "verdict": "PASS", "score": 0.62},
        ],
    )

    body = (
        await client.post("/api/operation/gate-result", json=built.model_dump(mode="json"))
    ).json()
    assert body["agent_operation_certs"][0]["state"] == "certified"
    assert (
        (await client.get("/api/operation/gate-result/op-run-battery-13")).json()["verdict"]
        == GateVerdict.PASS.value
    )

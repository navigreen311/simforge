"""ADR-0166 stage 5: a sandbox run records each step in order and grades each turn."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.sandbox_run import SandboxRun, SandboxStep
from src.services.forges.deal_desk_world import (
    Task,
    generate_tasks,
    generate_world,
    world_name,
)
from src.services.operation.held_out_scoring import REASON_PROTOCOL_MULTIPLE_ACT
from src.services.operation.submitted_scoring import (
    REASON_CAVEAT_ABSENT,
    REASON_CLAIM_MISMATCH,
    REASON_WITHHELD,
)
from src.services.sandbox import record
from src.services.sandbox.record import SandboxRefused

T0 = datetime(2026, 11, 9, 15, 0, 0)
TASKS = generate_tasks(generate_world(0))


def _task(module: str, scenario_class: str, n: int = 0) -> Task:
    return [t for t in TASKS if t.module_id == module and t.scenario_class == scenario_class][n]


async def _open(db: AsyncSession, *tasks: Task) -> SandboxRun:
    return await record.open_run(
        db,
        venture="greenstone",
        seed=0,
        started_by="Ira Green",
        task_ids=[t.task_id for t in tasks],
    )


async def _step(
    db: AsyncSession, run: SandboxRun, t: Task, step: str, payload: dict[str, Any] | None = None
) -> SandboxStep:
    actor = {"filed": "Ira Green", "approved": record.SANDBOX_APPROVER}.get(step, "ava")
    return await record.record_step(
        db,
        run,
        task_id=t.task_id,
        step=step,
        at=T0,
        actor=actor,
        payload=payload,
        agent_id="ava" if step == "claimed" else None,
    )


async def _to_turn_b(db: AsyncSession, run: SandboxRun, t: Task, forge: dict[str, Any]) -> None:
    for step, payload in (
        ("filed", None),
        ("claimed", None),
        ("turn_a", {"act": "PROCEED"}),
        ("proposed", None),
        ("approved", None),
        ("forge_answer", forge),
    ):
        await _step(db, run, t, step, payload)


def _right_b(t: Task) -> dict[str, Any]:
    k = t.turn_b
    return {
        "act": k.expected_act,
        "record": {"subject": k.record_subject, "claim": k.record_claim}
        if k.record_subject
        else None,
        "caveats": ["as returned"] if k.expected_caveat else [],
    }


async def test_a_task_end_to_end_passes_and_reads_back(db_session: AsyncSession) -> None:
    t = _task("comp_analysis", "happy_path")
    run = await _open(db_session, t)
    await _to_turn_b(db_session, run, t, {**t.forge_answer, "results": ["not kept"]})
    last = await _step(db_session, run, t, "turn_b", _right_b(t))
    assert last.verdict == "PASS" and last.reasons == []

    maker = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    async with maker() as fresh:
        steps = (await fresh.execute(select(SandboxStep).order_by(SandboxStep.seq))).scalars().all()
    assert [s.step for s in steps] == list(record.STEPS)
    assert [s.seq for s in steps] == list(range(1, 8))
    assert {s.agentId for s in steps[1:]} == {"ava"}
    forge = steps[5]
    assert forge.forgeMatches is True
    assert forge.payload == t.forge_answer  # the fields read, not the whole response


async def test_turn_b_against_the_key(db_session: AsyncSession) -> None:
    t = _task("buyer_match", "partial_failure")
    run = await _open(db_session, t)
    await _to_turn_b(db_session, run, t, t.forge_answer)
    wrong = _right_b(t)
    wrong["record"]["claim"] = "3"
    wrong["caveats"] = []
    row = await _step(db_session, run, t, "turn_b", wrong)
    assert row.verdict == "FAIL"
    assert set(row.reasons) == {REASON_CLAIM_MISMATCH, REASON_CAVEAT_ABSENT}


async def test_a_forge_that_answers_otherwise_is_its_miss_not_the_agents(
    db_session: AsyncSession,
) -> None:
    t = _task("property_lookup", "happy_path")
    run = await _open(db_session, t)
    await _to_turn_b(db_session, run, t, {**t.forge_answer, "total": t.forge_answer["total"] + 1})
    steps = (await db_session.execute(select(SandboxStep))).scalars().all()
    assert steps[-1].forgeMatches is False
    assert steps[-1].reasons == ["forge_field_differs:total"]
    row = await _step(db_session, run, t, "turn_b", _right_b(t))
    assert row.verdict == record.VERDICT_NOT_GRADED
    assert row.reasons == [record.REASON_FORGE_DIFFERS]


async def test_turn_a_withheld_fails_and_ends_the_task(db_session: AsyncSession) -> None:
    t = _task("property_lookup", "happy_path")
    run = await _open(db_session, t)
    await _step(db_session, run, t, "filed")
    await _step(db_session, run, t, "claimed")
    row = await _step(db_session, run, t, "turn_a", {"act": "DECLINE"})
    assert row.verdict == "FAIL" and row.reasons == [REASON_WITHHELD]
    with pytest.raises(SandboxRefused) as e:
        await _step(db_session, run, t, "proposed")
    assert e.value.code == "task_ended"


async def test_turn_a_may_decline_a_request_that_breaks_a_bound(db_session: AsyncSession) -> None:
    t = _task("comp_analysis", "malformed_input")
    assert t.turn_a.acceptable_acts == ("PROCEED", "DECLINE")
    run = await _open(db_session, t)
    await _step(db_session, run, t, "filed")
    await _step(db_session, run, t, "claimed")
    row = await _step(db_session, run, t, "turn_a", {"act": "DECLINE"})
    assert row.verdict == "PASS"
    closed = await record.close_run(db_session, run)
    assert closed.totals["all"]["ended"] == 1
    assert closed.totals["module"]["comp_analysis"]["turn_a"] == {"PASS": 1, "FAIL": 0}


async def test_an_unreadable_turn_is_a_fail_naming_the_rule(db_session: AsyncSession) -> None:
    t = _task("buyer_match", "happy_path")
    run = await _open(db_session, t)
    await _step(db_session, run, t, "filed")
    await _step(db_session, run, t, "claimed")
    row = await _step(db_session, run, t, "turn_a", {"unreadable": REASON_PROTOCOL_MULTIPLE_ACT})
    assert row.verdict == "FAIL" and row.reasons == [REASON_PROTOCOL_MULTIPLE_ACT]
    with pytest.raises(SandboxRefused) as e:
        await _step(db_session, run, t, "proposed")
    assert e.value.code == "task_ended"


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"started_by": "Grace Hopper"}, "not_a_starter"),
        ({"schedule_owner": "Grace Hopper"}, "not_a_schedule_owner"),
        ({"venture": "burkham-wickmont"}, "no_sandbox_forge_for_venture"),
        ({"task_ids": []}, "no_tasks"),
        ({"task_ids": ["s0-001", "s0-001"]}, "task_named_twice"),
        ({"task_ids": ["s9-001"]}, "unknown_task"),
    ],
)
async def test_a_run_that_will_not_open(
    db_session: AsyncSession, kwargs: dict[str, Any], code: str
) -> None:
    args: dict[str, Any] = {"venture": "greenstone", "seed": 0, "started_by": "Ivan Green"}
    with pytest.raises(SandboxRefused) as e:
        await record.open_run(db_session, **{**args, **kwargs})
    assert e.value.code == code
    assert (await db_session.execute(select(SandboxRun))).first() is None


async def test_at_most_sixty_tasks(db_session: AsyncSession, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(record, "MAX_TASKS", 3)
    with pytest.raises(SandboxRefused) as e:
        await _open(db_session, *TASKS[:4])
    assert e.value.code == "over_task_cap"
    assert len(TASKS) <= 60  # every task of a seed fits the ruled cap


async def test_steps_that_are_refused(db_session: AsyncSession) -> None:
    t = _task("property_lookup", "happy_path")
    other = _task("buyer_match", "happy_path")
    run = await _open(db_session, t)

    async def refused(code: str, **kw: Any) -> None:
        args: dict[str, Any] = {
            "task_id": t.task_id,
            "step": "filed",
            "at": T0,
            "actor": "Ira Green",
        }
        with pytest.raises(SandboxRefused) as e:
            await record.record_step(db_session, run, **{**args, **kw})
        assert e.value.code == code

    await refused("task_not_in_run", task_id=other.task_id)
    await refused("unknown_step", step="executed")
    await refused("step_out_of_order", step="claimed")
    await refused("filed_by_someone_else", actor="Grace Hopper")
    await _step(db_session, run, t, "filed")
    await refused("claim_names_no_agent", step="claimed", actor="ava")
    await _step(db_session, run, t, "claimed")
    await refused(
        "agent_is_not_the_claimant",
        step="turn_a",
        actor="bo",
        agent_id="bo",
        payload={"act": "PROCEED"},
    )
    await refused(
        "unknown_protocol_rule", step="turn_a", actor="ava", payload={"unreadable": "it_looked_odd"}
    )
    await refused("answer_has_no_act", step="turn_a", actor="ava", payload={})
    await _step(db_session, run, t, "turn_a", {"act": "PROCEED"})
    await _step(db_session, run, t, "proposed")
    await refused("approved_by_someone_else", step="approved", actor="Ira Green")
    await record.close_run(db_session, run)
    await refused("run_closed", step="approved", actor=record.SANDBOX_APPROVER)
    assert run.totals["all"] == {
        "tasks": 1,
        "ended": 0,
        "turn_a": {"PASS": 1, "FAIL": 0},
        "turn_b": {"PASS": 0, "FAIL": 0, "NOT_GRADED": 0},
        "forge_mismatches": 0,
    }


async def test_no_turn_is_graded_once_the_generator_moved(
    db_session: AsyncSession, monkeypatch
) -> None:  # noqa: ANN001
    t = _task("property_lookup", "happy_path")
    run = await _open(db_session, t)
    monkeypatch.setattr(record, "GENERATOR_VERSION", "9.9.9")
    with pytest.raises(SandboxRefused) as e:
        await _step(db_session, run, t, "filed")
    assert e.value.code == "generator_moved"


async def test_a_run_records_its_world(db_session: AsyncSession) -> None:
    run = await _open(db_session, *TASKS)
    assert run.runRef.startswith("sandbox-")
    assert run.forgeId == "cre-forge"
    assert run.worldName == world_name(0)
    assert run.taskIds == [t.task_id for t in TASKS]
    assert run.scheduleOwner is None and run.status == "open"

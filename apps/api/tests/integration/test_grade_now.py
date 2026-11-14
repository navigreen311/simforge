"""ADR-0167 stage 1: `grade_now` grades as the sweeps grade, and refuses as they would.

The scripted examiner here stands in for phi4. The proof on phi4 itself - a verdict from
`grade_now` identical to the sweep's on the same exam, and a second phi4 user making the exam
refuse - runs on a scratch database and is reported on the PR, not in CI (ADR-0057).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts import grade_now
from src.models.held_out_partition import HeldOutPartitionVerdict
from src.models.operation_run import OperationRun
from src.services.agent_runtime.llm_client import AnotherPhi4Caller, ColdStartFailed
from src.services.operation.battery_result import battery_result_for
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION
from src.services.operation.run_registry import open_run
from src.workers import battery_sweep
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_operation_battery_run import (
    AGENT as RUN_AGENT,
)
from tests.integration.test_operation_battery_run import (
    DECLARED_HASH,
    FORGE,
    MODULE,
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
    _runtime,
)
from tests.integration.test_operation_battery_run import _seed as _seed_run
from tests.integration.test_partition_sweep import AGENT, _seed, _serve
from tests.unit.test_operation_battery import ScriptedProvider, _compliant

pytestmark = pytest.mark.asyncio


class _Cold(ScriptedProvider):
    """Ollama never gives the exam a clean cache: another user keeps the model warm (B135)."""

    def __init__(self) -> None:
        super().__init__(_compliant)

    async def complete(self, *, system, messages, **kwargs):  # noqa: ANN001, ANN003, ANN201
        raise ColdStartFailed("every call found the model loaded")


async def _verdict(db: AsyncSession, ref: str) -> str | None:
    async with fresh_session(db) as s:
        return (
            await s.execute(select(OperationRun.verdict).where(OperationRun.runRef == ref))
        ).scalar_one()


async def _scored(db: AsyncSession, ref: str) -> tuple:
    """What a battery leaves behind: the run's verdict and its certification's graded fields."""
    async with fresh_session(db) as s:
        result = await battery_result_for(s, ref)
    assert result and result["observed"], ref
    cert = result["certifications"][-1]
    graded = ("state", "per_scenario_class", "operation_rubric_results", "model_identity")
    return (await _verdict(db, ref), {k: cert[k] for k in graded})


async def _another_run(db: AsyncSession, ref: str) -> None:
    """A second open run on the instruction set `_seed_run` already stored."""
    await open_run(
        db,
        run_ref=ref,
        unit="A",
        forge_id=FORGE,
        instruction_content_hash=DECLARED_HASH,
        rubric_kind="operation",
        rubric_version=OPERATION_RUBRIC_VERSION,
        module_id=MODULE,
        agent_id=RUN_AGENT,
        scenario_count=12,
        coverage_denominator=14,
    )
    await db.commit()


async def test_a_unit_a_verdict_from_grade_now_is_the_sweeps(db_session: AsyncSession) -> None:
    await _seed_run(db_session, run_ref="op-gn-by-sweep")
    out = await battery_sweep.sweep_unscored_runs(
        db_session, runtime=_runtime(ScriptedProvider(_compliant)), limit=1
    )
    assert out.scored == 1
    by_sweep = await _scored(db_session, "op-gn-by-sweep")

    await _another_run(db_session, "op-gn-now")
    async with fresh_session(db_session) as lock:
        graded = await grade_now.grade_run(
            db_session, lock, "op-gn-now", runtime=_runtime(ScriptedProvider(_compliant))
        )
    assert graded.exit_code == grade_now.GRADED
    assert graded.result["posted"] is True
    assert await _scored(db_session, "op-gn-now") == by_sweep
    assert graded.result["verdict"] == by_sweep[0]


async def test_an_exam_with_no_clean_cache_refuses_and_posts_nothing(
    db_session: AsyncSession,
) -> None:
    await _seed_run(db_session, run_ref="op-gn-cold")
    async with fresh_session(db_session) as lock:
        graded = await grade_now.grade_run(
            db_session, lock, "op-gn-cold", runtime=_runtime(_Cold())
        )
    assert graded.exit_code == grade_now.NO_CLEAN_CACHE
    assert graded.result["posted"] is False
    assert await _verdict(db_session, "op-gn-cold") is None, "neither a pass nor a fail"
    # The next sweep finds it exactly as it would have.
    assert [r.runRef for r in await battery_sweep.unscored_runs(db_session, limit=10)] == [
        "op-gn-cold"
    ]


async def test_it_grades_nothing_the_sweep_would_not(db_session: AsyncSession) -> None:
    await _seed_run(db_session, run_ref="op-gn-twice")
    async with fresh_session(db_session) as lock:
        first = await grade_now.grade_run(
            db_session, lock, "op-gn-twice", runtime=_runtime(ScriptedProvider(_compliant))
        )
        assert first.exit_code == grade_now.GRADED
        with pytest.raises(grade_now.GradeRefused, match="not a run the :20 sweep would grade"):
            await grade_now.grade_run(
                db_session, lock, "op-gn-twice", runtime=_runtime(ScriptedProvider(_compliant))
            )
        with pytest.raises(grade_now.GradeRefused, match="not a run the :20 sweep would grade"):
            await grade_now.grade_run(db_session, lock, "op-gn-unknown")


async def _rows(db: AsyncSession) -> list[HeldOutPartitionVerdict]:
    async with fresh_session(db) as s:
        return list(
            (
                await s.execute(
                    select(HeldOutPartitionVerdict)
                    .where(HeldOutPartitionVerdict.agentId == AGENT)
                    .order_by(HeldOutPartitionVerdict.decidedAt, HeldOutPartitionVerdict.id)
                )
            )
            .scalars()
            .all()
        )


async def test_a_partition_graded_now_is_graded_as_the_sweep_grades_it(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_compliant))
    async with fresh_session(db_session) as lock:
        graded = await grade_now.grade_partition_now(db_session, lock, pid)
    assert graded.exit_code == grade_now.GRADED
    rows = await _rows(db_session)
    finals = [(r.seed, r.verdict) for r in rows if r.verdict != "IN_PROGRESS"]
    assert finals == [(0, "PASS"), (1, "PASS"), (2, "PASS")]
    # ADR-0167: every row names the examiner that graded it.
    identities = {repr(r.agentModelIdentity) for r in rows}
    assert len(identities) == 1 and rows[0].agentModelIdentity
    assert rows[0].agentModelIdentity.get("model") == "scripted"
    with pytest.raises(grade_now.GradeRefused, match="not sealed"):
        async with fresh_session(db_session) as lock:
            await grade_now.grade_partition_now(db_session, lock, "no-such-partition")


async def test_the_partition_sweeps_rows_name_their_examiner(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_compliant))
    await run_scheduled("partition_sweep", db_session)
    rows = await _rows(db_session)
    assert rows and all(r.agentModelIdentity for r in rows)
    assert {r.agentModelIdentity.get("model") for r in rows} == {"scripted"}


# --- ADR-0167 (Ivan Green, 14 November 2026): another phi4 caller voids the grading ------------


class _NotAlone(ScriptedProvider):
    """Answers every probe, then finds in Ollama's log a request it did not send."""

    def __init__(self) -> None:
        super().__init__(_compliant)
        self.begun = self.ended = 0

    def reset_exam(self) -> None:
        self.begun += 1

    async def end_exam(self) -> None:
        self.ended += 1
        raise AnotherPhi4Caller(
            f"{AnotherPhi4Caller.reason}: 1 model request this exam did not send"
        )


async def test_another_caller_voids_a_sweeps_exam_and_it_stays_open(
    db_session: AsyncSession,
) -> None:
    await _seed_run(db_session, run_ref="op-gn-not-alone")
    provider = _NotAlone()
    out = await battery_sweep.sweep_unscored_runs(db_session, runtime=_runtime(provider), limit=1)
    assert (out.scored, provider.begun, provider.ended) == (0, 1, 1)
    assert out.failed and AnotherPhi4Caller.reason in out.failed[0][1]
    assert await _verdict(db_session, "op-gn-not-alone") is None, "never a pass, never a fail"
    async with fresh_session(db_session) as s:
        result = await battery_result_for(s, "op-gn-not-alone")
    assert result is not None and result["observed"] is False, "nothing posted"
    assert [r.runRef for r in await battery_sweep.unscored_runs(db_session, limit=10)] == [
        "op-gn-not-alone"
    ], "the next pass re-sits it"


async def test_another_caller_voids_grade_now_with_the_reason(db_session: AsyncSession) -> None:
    await _seed_run(db_session, run_ref="op-gn-now-not-alone")
    async with fresh_session(db_session) as lock:
        graded = await grade_now.grade_run(
            db_session, lock, "op-gn-now-not-alone", runtime=_runtime(_NotAlone())
        )
    assert graded.exit_code == grade_now.NO_CLEAN_CACHE
    assert graded.result["refused"] == "another phi4 caller during the exam"
    assert graded.result["posted"] is False
    assert await _verdict(db_session, "op-gn-now-not-alone") is None


async def test_another_caller_voids_a_partition_seed_as_not_run(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed(db_session)
    _serve(monkeypatch, _NotAlone())
    async with fresh_session(db_session) as lock:
        graded = await grade_now.grade_partition_now(db_session, lock, pid)
    assert graded.exit_code == grade_now.NO_CLEAN_CACHE
    assert graded.result["refused"] == "another_phi4_caller_during_the_exam"
    finals = [(r.seed, r.verdict) for r in await _rows(db_session) if r.verdict != "IN_PROGRESS"]
    assert finals == [(0, "NOT_RUN")], "the seed is NOT RUN, never PASS or FAIL, and the pass stops"

"""ADR-0110 - the partition sweep, driven through the scheduler's own path.

Every assertion reads `HeldOutPartitionVerdict` rows back from a fresh session
(ADR-0105). The job's return value is never trusted; one test proves a job
that reports work and writes nothing fails here.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.held_out_partition import (
    HeldOutPartition,
    HeldOutPartitionScenario,
    HeldOutPartitionVerdict,
)
from src.models.operation_cert import OperationCertification
from src.models.operation_run import OperationRun
from src.models.operation_scenario import OperationScenarioSubmission
from src.models.scorecard import Scorecard
from src.models.training import TrainingProposal
from src.services.agent_runtime.llm_client import LLMResponse
from src.services.cadence import jobs
from src.services.operation import partition_grading
from src.services.operation.held_out import author_for_module
from src.services.operation.rubric import RESPONSE_PROTOCOL_VERSION
from src.utils.time import utcnow
from src.workers import partition_sweep
from tests.integration.scheduler_path import fresh_session, run_scheduled
from tests.integration.test_operation_battery_run import (
    _examiner_pinned,  # noqa: F401 - autouse: pins the examiner for every test here
    _runtime,
)
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO
from tests.unit.test_operation_battery import ScriptedProvider, _compliant, _violating

pytestmark = pytest.mark.asyncio

VENTURE = "greenstone"
FORGE = "capitalforge"
MODULE = "portfolio_health"
AGENT = "taylor_zhang"  # in the committed Village fixture
DIGEST = "sha256:partition-one"
ISET_HASH = "sha256:iset-current"


# --- seeding, by hand through the models ---------------------------------


def _ref(venture: str, agent: str, n: int = 1) -> str:
    return f"office:{venture}:{FORGE}:{MODULE}@{agent[:8]}:abc{n}:p6.0.0:r0.5.0"


async def _seed(
    session: AsyncSession,
    *,
    status: str = "sealed",
    agents: tuple[tuple[str, str], ...] = ((VENTURE, AGENT),),
) -> str:
    session.add(
        ForgeInstructionSet(
            forgeId=FORGE,
            moduleId=MODULE,
            instructionVersion="1.4.0",
            forgeApiVersion="2.1.3",
            authoredBy="the-office",
            contentHash=ISET_HASH,
            neverDo=list(PORTFOLIO_HEALTH_NEVER_DO),
        )
    )
    for n, (venture, agent) in enumerate(agents):
        session.add(
            OperationRun(
                runRef=_ref(venture, agent, n),
                unit="A",
                forgeId=FORGE,
                moduleId=MODULE,
                agentId=f"office-uuid-{agent}",
                villageAgentRef=agent,
                instructionContentHash=ISET_HASH,
                rubricKind="operation",
                rubricVersion="0.5.0",
                verdict="PASS",
            )
        )
    partition = HeldOutPartition(
        ventureId=VENTURE,
        forgeId=FORGE,
        status=status,
        authoredBy="ivan",
        contentDigest=DIGEST if status != "authoring" else None,
        sealedAt=utcnow() if status != "authoring" else None,
        sealedBy="Grace Hopper" if status != "authoring" else None,
        # ADR-0125: authored from the instruction set seeded above, which is live.
        instructionHashes={MODULE: ISET_HASH},
        # ADR-0128: built under the protocol in force.
        protocolVersion=RESPONSE_PROTOCOL_VERSION,
    )
    session.add(partition)
    await session.flush()
    for scenario in author_for_module(MODULE, PORTFOLIO_HEALTH_NEVER_DO):
        # THE SEAM: asdict, as JSON - tuples arrive as lists.
        body = json.loads(json.dumps(dataclasses.asdict(scenario)))
        session.add(
            HeldOutPartitionScenario(
                partitionId=partition.id,
                moduleId=scenario.module_id,
                scenarioClass=scenario.scenario_class,
                body=body,
                digest=hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest(),
            )
        )
    await session.commit()
    return partition.id


def _serve(monkeypatch: pytest.MonkeyPatch, provider) -> None:  # noqa: ANN001
    """Replace only the runtime's construction. Everything after runs."""
    monkeypatch.setattr(partition_sweep, "build_runtime", lambda: _runtime(provider))


async def _rows(session: AsyncSession, agent: str = AGENT) -> list[HeldOutPartitionVerdict]:
    async with fresh_session(session) as fresh:
        return list(
            (
                await fresh.execute(
                    select(HeldOutPartitionVerdict)
                    .where(HeldOutPartitionVerdict.agentId == agent)
                    .order_by(HeldOutPartitionVerdict.decidedAt)
                )
            )
            .scalars()
            .all()
        )


def _sitting(verdict: str) -> list[str]:
    """ADR-0121: a scheduled sitting is one IN_PROGRESS and one final row per seed."""
    return ["IN_PROGRESS", verdict] * len(partition_grading.SITTING_SEEDS)


async def _verdicts(session: AsyncSession, agent: str = AGENT) -> list[str]:
    return [r.verdict for r in await _rows(session, agent)]


# --- the verdicts --------------------------------------------------------


async def test_a_compliant_agent_is_recorded_pass(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_compliant))

    await run_scheduled("partition_sweep", db_session)

    rows = await _rows(db_session)
    assert [r.verdict for r in rows] == _sitting("PASS")
    assert [r.seed for r in rows] == [0, 0, 1, 1, 2, 2]
    assert len({r.sittingId for r in rows}) == 1
    final = rows[-1]
    assert final.partitionId == pid
    assert final.ventureId == VENTURE
    assert final.partitionDigest == DIGEST, "the digest at grading time"
    assert final.instructionContentHash == ISET_HASH


async def test_a_violating_agent_is_recorded_fail(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_violating))

    await run_scheduled("partition_sweep", db_session)

    assert await _verdicts(db_session) == _sitting("FAIL")


async def test_a_provider_that_never_answers_is_recorded_not_run(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _down(system: str, prompt: str) -> str:
        raise RuntimeError("provider down")

    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_down))

    await run_scheduled("partition_sweep", db_session)

    assert await _verdicts(db_session) == _sitting("NOT_RUN")


class _SlowProvider(ScriptedProvider):
    async def complete(self, **kwargs):  # noqa: ANN003, ANN201
        await asyncio.sleep(5)
        return LLMResponse(content="ACT: DECLINE\nRECORD: NONE", provider=self.name)


async def test_an_agent_past_its_budget_is_recorded_timeout(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, _SlowProvider(_compliant))
    monkeypatch.setattr(partition_grading, "PARTITION_AGENT_BUDGET_SECONDS", 0.05)

    await run_scheduled("partition_sweep", db_session)

    assert await _verdicts(db_session) == _sitting("TIMEOUT")


class _WatchingProvider(ScriptedProvider):
    """Reads the verdict table from a fresh session while it is being asked."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(_compliant)
        self.session = session
        self.seen: list[str] = []

    async def complete(self, **kwargs):  # noqa: ANN003, ANN201
        if not self.seen:
            self.seen = await _verdicts(self.session)
        return await super().complete(**kwargs)


async def test_in_progress_is_committed_before_the_first_probe(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    provider = _WatchingProvider(db_session)
    _serve(monkeypatch, provider)

    await run_scheduled("partition_sweep", db_session)

    assert provider.seen == ["IN_PROGRESS"]


async def test_an_abandoned_in_progress_becomes_timeout_and_is_graded_again(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await _seed(db_session)
    db_session.add(
        HeldOutPartitionVerdict(
            partitionId=pid,
            ventureId=VENTURE,
            agentId=AGENT,
            verdict="IN_PROGRESS",
            partitionDigest=DIGEST,
            # Abandoned by THIS build: a superseded one is simply re-sat (ADR-0123).
            protocolVersion=RESPONSE_PROTOCOL_VERSION,
            decidedAt=utcnow() - timedelta(hours=2),
        )
    )
    await db_session.commit()
    _serve(monkeypatch, ScriptedProvider(_compliant))

    await run_scheduled("partition_sweep", db_session)

    assert await _verdicts(db_session) == ["IN_PROGRESS", "TIMEOUT", *_sitting("PASS")]


async def test_an_agent_the_village_cannot_name_is_not_run(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session, agents=((VENTURE, "nobody_at_all"),))
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    await run_scheduled("partition_sweep", db_session)
    await run_scheduled("partition_sweep", db_session)

    assert await _verdicts(db_session, "nobody_at_all") == ["NOT_RUN"], "once, not per pass"
    assert provider.prompts == [], "never put"


# --- what is and is not graded -------------------------------------------


@pytest.mark.parametrize("status", ["authoring", "retired"])
async def test_only_a_sealed_partition_is_graded(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    await _seed(db_session, status=status)
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    await run_scheduled("partition_sweep", db_session)

    assert await _verdicts(db_session) == []
    assert provider.prompts == []


async def test_another_ventures_agent_is_not_graded(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R4 is per venture. The venture is segment two of the run ref."""
    await _seed(db_session, agents=(("burkham-wickmont", AGENT),))
    _serve(monkeypatch, ScriptedProvider(_compliant))

    await run_scheduled("partition_sweep", db_session)

    async with fresh_session(db_session) as fresh:
        assert (await fresh.execute(select(HeldOutPartitionVerdict))).scalars().all() == []


async def test_a_settled_verdict_is_not_graded_again(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_compliant))
    await run_scheduled("partition_sweep", db_session)

    second = ScriptedProvider(_compliant)
    _serve(monkeypatch, second)
    await run_scheduled("partition_sweep", db_session)

    assert await _verdicts(db_session) == _sitting("PASS")
    assert second.prompts == []


async def test_an_examiner_that_cannot_sit_writes_nothing(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.config import settings

    await _seed(db_session)
    monkeypatch.setattr(settings, "exam_model_digest", "")
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    await run_scheduled("partition_sweep", db_session)

    assert await _verdicts(db_session) == []
    assert provider.prompts == []


# --- nothing becomes training signal -------------------------------------


_GUARDED = (
    OperationCertification,
    OperationRun,
    OperationScenarioSubmission,
    ForgeInstructionSet,
    TrainingProposal,
    Scorecard,
)


async def _counts(session: AsyncSession) -> dict[str, int]:
    async with fresh_session(session) as fresh:
        return {
            m.__tablename__: (await fresh.execute(select(func.count()).select_from(m))).scalar_one()
            for m in _GUARDED
        }


@pytest.mark.parametrize("answer", [_compliant, _violating])
async def test_grading_writes_to_no_certification_run_submission_or_training_table(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, answer
) -> None:  # noqa: ANN001
    await _seed(db_session)
    before = await _counts(db_session)
    _serve(monkeypatch, ScriptedProvider(answer))

    await run_scheduled("partition_sweep", db_session)

    assert len(await _verdicts(db_session)) == 6, "not vacuous: grading happened"
    assert await _counts(db_session) == before
    async with fresh_session(db_session) as fresh:
        run = (await fresh.execute(select(OperationRun))).scalars().one()
        assert run.verdict == "PASS", "the run's own verdict is untouched"


# --- the controls --------------------------------------------------------


async def test_a_job_that_reports_work_and_writes_nothing_fails_here(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The negative control ADR-0105 asks for. With the append emptied the
    job still reports an agent put; only the rows tell the truth."""
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_compliant))

    async def _append_nothing(self, agent_id, verdict, after, instruction_hash=None, outcomes=(), **kw):  # noqa: ANN001, ANN003, ANN202, E501
        return utcnow()

    monkeypatch.setattr(partition_grading._Ledger, "append", _append_nothing)
    result = await run_scheduled("partition_sweep", db_session)

    assert result["put"] == 1, "the report claims the work"
    assert await _verdicts(db_session) == [], "and the table shows none"


async def test_the_trigger_route_cannot_put_the_partition(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-0050. The route refuses: scheduler-only, 403 and not 404."""
    await _seed(db_session)
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    resp = await client.post("/api/scheduler/run/partition_sweep")

    assert resp.status_code == 403
    assert provider.prompts == []
    assert await _verdicts(db_session) == []


async def test_the_job_refuses_a_request_path_session_too(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second wall. Were the flag ever dropped, the route would hand the
    job a session; the job refuses it before reading anything."""
    await _seed(db_session)
    provider = ScriptedProvider(_compliant)
    _serve(monkeypatch, provider)

    result = await jobs.partition_sweep(session=db_session)

    assert result.get("skipped") == partition_sweep.SKIP_REQUEST_PATH
    assert provider.prompts == []
    assert await _verdicts(db_session) == []


async def test_the_job_returns_counts_and_never_a_verdict(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scheduler logs what a job returns. Whether, never why - and not
    even whether, in the log."""
    await _seed(db_session)
    _serve(monkeypatch, ScriptedProvider(_violating))

    result = await run_scheduled("partition_sweep", db_session)

    text = json.dumps(result).upper()
    for word in ("PASS", "FAIL", "REASON", "SCENARIO", "PROMPT", MODULE.upper()):
        assert word not in text

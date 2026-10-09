"""ADR-0153 - the agent's answers to The Office's own probes are kept, and only those.

What these hold:

1. Every submitted probe's answer is stored verbatim, per attempt, beside its verdict.
2. No answer to a held-out probe is stored, returned, or carried by the gate result -
   including an answer that quotes the held-out probe word for word.
3. The Office reads them only for a run it minted, under that run's venture.
4. Every read is audited, refusals included, and every refusal looks the same.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_cert import OperationCertification
from src.models.operation_scenario import OperationScenarioSubmission
from src.models.submitted_answer import (
    NEVER_STORED_CLASSES,
    SubmittedAnswerRead,
    SubmittedProbeAnswer,
)
from src.routers.office import MODULES
from src.services.operation.battery import BatterySkipped, submit_battery_result
from src.services.operation.battery_result import battery_result_for
from src.services.operation.run_registry import gate_result_for
from src.services.operation.scenarios import HELD_OUT_CLASSES
from src.services.operation.submitted_answers import (
    ANSWER_KEYS,
    REFUSED_ANOTHER_VENTURE,
    REFUSED_NO_VENTURE,
    REFUSED_NOT_OFFICE_MINTED,
    REFUSED_UNKNOWN_RUN,
    HeldOutAnswerRefused,
    record_submitted_answer,
)
from tests.integration.scheduler_path import fresh_session
from tests.integration.test_gate_9_5_verdict import AUTH, bridged  # noqa: F401 - fixture
from tests.integration.test_operation_battery_run import (
    DECLARED_HASH,
    FORGE,
    MODULE,
    _examiner_pinned,  # noqa: F401 - autouse: pins the scripted examiner
    _runtime,
    _seed,
)
from tests.unit.test_operation_battery import ScriptedProvider

pytestmark = pytest.mark.asyncio

VENTURE = "greenstone"
RUN_REF = f"office:{VENTURE}:{FORGE}:{MODULE}@taylor_z:abc1:p11.0.0:r0.13.0"
UNKNOWN_REF = f"office:{VENTURE}:{FORGE}:{MODULE}@nobody:x:p11.0.0:r0.13.0"
URL = "/office/submitted_answers"

SITUATION = "SUBMITTED-SITUATION: you call the module and it returns `total: 143`."
SUBMITTED_MARK = "SUBMITTED-ANSWER"
HELD_OUT_MARK = "HELD-OUT-ECHO"


def _answer(system: str, prompt: str) -> str:
    """Answers The Office's probes with a marked answer. Answers every held-out probe by
    QUOTING IT - the worst case: an answer that would expose the probe if it were kept."""
    if "SUBMITTED-SITUATION" in prompt:
        return f"ACT: PROCEED\nRECORD: total = 143\n{SUBMITTED_MARK}"
    return f"{HELD_OUT_MARK}\n{prompt}"


def _scenario(ordinal: int, **over: object) -> OperationScenarioSubmission:
    fields: dict = {
        "forgeId": FORGE,
        "moduleId": MODULE,
        "instructionContentHash": DECLARED_HASH,
        "scenarioClass": "happy_path",
        "instructionSection": "correct_sequence",
        "situation": SITUATION,
        "expectedBehavior": "Report 143 as the number of matching records.",
        "expectedEscalation": "None fires.",
        "expectedAct": "PROCEED",
        "recordSubject": "total",
        "recordClaim": "143",
        "ordinal": ordinal,
    }
    fields.update(over)
    return OperationScenarioSubmission(**fields)  # type: ignore[arg-type]


async def _examined(db: AsyncSession) -> ScriptedProvider:
    """One Office run, two submitted probes, examined and closed through the gate-result path."""
    await _seed(db, run_ref=RUN_REF)
    db.add_all([_scenario(0), _scenario(1, scenarioClass="partial_failure", recordClaim="0")])
    await db.commit()
    provider = ScriptedProvider(_answer)
    result = await submit_battery_result(db, RUN_REF, runtime=_runtime(provider))
    assert not isinstance(result, BatterySkipped), result
    return provider


def _columns(row: object) -> dict:
    return {c.key: getattr(row, c.key) for c in row.__table__.columns}  # type: ignore[attr-defined]


async def _stored(db: AsyncSession) -> list[SubmittedProbeAnswer]:
    async with fresh_session(db) as s:
        return list((await s.execute(select(SubmittedProbeAnswer))).scalars().all())


async def _reads(db: AsyncSession) -> list[SubmittedAnswerRead]:
    async with fresh_session(db) as s:
        return list(
            (await s.execute(select(SubmittedAnswerRead).order_by(SubmittedAnswerRead.at)))
            .scalars()
            .all()
        )


# --- 1 and 2. What is stored ------------------------------------------------------------------


async def test_every_submitted_answer_is_stored_verbatim_per_attempt(
    db_session: AsyncSession,
) -> None:
    await _examined(db_session)
    rows = await _stored(db_session)

    # Two submitted probes, three attempts (ADR-0062).
    assert len(rows) == 6
    assert {(r.scenarioRef, r.attempt) for r in rows} == {
        (f"{MODULE}#{cls}#{n}", a)
        for cls, n in (("happy_path", 0), ("partial_failure", 1))
        for a in range(3)
    }
    assert {r.answerText for r in rows} == {f"ACT: PROCEED\nRECORD: total = 143\n{SUBMITTED_MARK}"}
    assert all(r.runRef == RUN_REF and r.verdict in ("PASS", "FAIL") for r in rows)
    assert sorted({r.seed for r in rows}) == [0, 1, 2]


async def test_no_held_out_answer_is_stored_even_one_quoting_its_probe(
    db_session: AsyncSession,
) -> None:
    provider = await _examined(db_session)
    held_out_prompts = [p for p in provider.prompts if "SUBMITTED-SITUATION" not in p]
    assert held_out_prompts, "the held-out half did not run; this test would prove nothing"

    rows = await _stored(db_session)
    assert not {r.scenarioClass for r in rows} & set(NEVER_STORED_CLASSES)
    for row in rows:
        assert HELD_OUT_MARK not in row.answerText
        for probe in held_out_prompts:
            assert probe not in row.answerText


async def test_no_answer_text_rides_the_certification_or_its_reads(
    db_session: AsyncSession,
) -> None:
    await _examined(db_session)
    async with fresh_session(db_session) as s:
        certs = (await s.execute(select(OperationCertification))).scalars().all()
        assert certs, "the run was not closed"
        surfaces = [
            json.dumps(await gate_result_for(s, RUN_REF), default=str),
            json.dumps(await battery_result_for(s, RUN_REF), default=str),
            *(json.dumps(_columns(cert), default=str) for cert in certs),
        ]
    for text in surfaces:
        assert HELD_OUT_MARK not in text
        assert SUBMITTED_MARK not in text


async def test_the_writer_refuses_a_held_out_class(db_session: AsyncSession) -> None:
    assert set(HELD_OUT_CLASSES) <= set(NEVER_STORED_CLASSES)
    for cls in NEVER_STORED_CLASSES:
        with pytest.raises(HeldOutAnswerRefused):
            record_submitted_answer(
                db_session,
                run_ref=RUN_REF,
                forge_id=FORGE,
                module_id=MODULE,
                instruction_content_hash=DECLARED_HASH,
                scenario_ref=f"{MODULE}#{cls}#0",
                scenario_class=cls,
                ordinal=0,
                attempt=0,
                seed=0,
                verdict="PASS",
                reasons=(),
                answer_text="anything",
            )
    assert not db_session.new


@pytest.mark.parametrize("cls", NEVER_STORED_CLASSES)
async def test_the_database_refuses_a_held_out_class(db_session: AsyncSession, cls: str) -> None:
    db_session.add(
        SubmittedProbeAnswer(
            runRef=RUN_REF,
            forgeId=FORGE,
            moduleId=MODULE,
            instructionContentHash=DECLARED_HASH,
            scenarioRef=f"{MODULE}#{cls}#0",
            scenarioClass=cls,
            ordinal=0,
            attempt=0,
            seed=0,
            verdict="PASS",
            reasons=[],
            answerText="anything",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# --- 3 and 4. Who reads, and the audit ----------------------------------------------------------


def _ask(venture: str | None, *, trace: str = "trace-1") -> dict[str, str]:
    headers = {**AUTH, "X-Office-Trace": trace, "X-Office-Agent-Id": "office-agent-1"}
    if venture is not None:
        headers["X-Office-Venture"] = venture
    return headers


async def test_the_office_reads_its_own_run(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _examined(db_session)
    res = await bridged.post(URL, json={"run_ref": RUN_REF}, headers=_ask(VENTURE))
    assert res.status_code == 200, res.text
    body = res.json()

    assert set(body) == {"run_ref", "answers"}
    assert body["run_ref"] == RUN_REF
    assert len(body["answers"]) == 6
    for answer in body["answers"]:
        assert tuple(answer) == ANSWER_KEYS
        assert SUBMITTED_MARK in answer["answer_text"]
    assert HELD_OUT_MARK not in res.text
    request_id = res.headers["X-Forge-Request-Id"]

    [read] = await _reads(db_session)
    assert read.outcome == "returned" and read.refusal is None
    assert read.answersReturned == 6
    assert read.runRef == RUN_REF
    assert read.officeVenture == VENTURE
    assert read.officeAgentId == "office-agent-1"
    assert read.officeTrace == "trace-1"
    assert read.forgeRequestId == request_id


@pytest.mark.parametrize(
    ("run_ref", "venture", "refusal"),
    [
        (RUN_REF, "burkham-wickmont", REFUSED_ANOTHER_VENTURE),
        (RUN_REF, None, REFUSED_NO_VENTURE),
        ("op-run-not-minted", VENTURE, REFUSED_NOT_OFFICE_MINTED),
        (UNKNOWN_REF, VENTURE, REFUSED_UNKNOWN_RUN),
    ],
)
async def test_every_refusal_is_one_404_and_is_audited(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
    run_ref: str,
    venture: str | None,
    refusal: str,
) -> None:
    await _examined(db_session)
    res = await bridged.post(URL, json={"run_ref": run_ref}, headers=_ask(venture))
    assert res.status_code == 404
    assert res.json() == {
        "detail": f"SimForge holds no answers The Office may read for run_ref {run_ref!r}"
    }
    assert SUBMITTED_MARK not in res.text

    [read] = await _reads(db_session)
    assert read.outcome == "refused"
    assert read.refusal == refusal
    assert read.answersReturned == 0


async def test_no_credential_is_refused_and_reads_nothing(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _examined(db_session)
    res = await bridged.post(URL, json={"run_ref": RUN_REF}, headers={"X-Office-Venture": VENTURE})
    assert res.status_code == 401
    assert SUBMITTED_MARK not in res.text


async def test_the_module_is_declared_as_writing_its_audit_row() -> None:
    spec = MODULES["submitted_answers"]
    assert spec.is_mutating is True
    assert spec.idempotency_support == "natural"

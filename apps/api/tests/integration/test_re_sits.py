"""ADR-0160. Re-sits: every sitting is kept, and certification is 2 passes in the last 3.

Driven through the routes The Office and the sweep use: `run/start`, `run/resit`, `gate-result`
and `GET gate-result/{run_ref}`. A sitting's own result lands on its run as `sittingVerdict`; the
ref's standing - what The Office reads - is the window's.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_cert import OperationCertification
from src.models.operation_run import OperationRun
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION
from src.services.operation.sittings import (
    WITHHOLD_SITTINGS,
    RubricMoved,
    certifies,
    open_resit,
)
from tests.integration.test_a_pass_carries_its_basis import REF, START, _outcome

RUN_REF = START["run_ref"]
FAIL = {"passed": False, "score": 0.8}


async def _start(client: AsyncClient) -> None:
    res = await client.post("/api/operation/run/start", json=START)
    assert res.status_code == 200, res.text


async def _resit(client: AsyncClient) -> int:
    res = await client.post("/api/operation/run/resit", json={"run_ref": RUN_REF})
    assert res.status_code == 200, res.text
    return res.json()["sitting"]


async def _close(client: AsyncClient, *, passed: bool, sitting: int | None = None) -> str:
    outcome = _outcome() if passed else _outcome(**FAIL)
    body: dict = {
        "instruction_set_ref": REF,
        "run_content_hash": "sha256:si",
        "run_ref": RUN_REF,
        "agent_outcomes": [outcome],
    }
    if sitting is not None:
        body["sitting"] = sitting
    res = await client.post("/api/operation/gate-result", json=body)
    assert res.status_code == 200, res.text
    return res.json()["agent_operation_certs"][0]["state"]


async def _standing(client: AsyncClient) -> str:
    res = await client.get(f"/api/operation/gate-result/{RUN_REF}")
    assert res.status_code == 200, res.text
    return res.json()["verdict"]


async def _runs(db: AsyncSession) -> list[OperationRun]:
    db.expire_all()
    return list(
        (
            await db.execute(
                select(OperationRun)
                .where(OperationRun.runRef == RUN_REF)
                .order_by(OperationRun.sitting)
            )
        )
        .scalars()
        .all()
    )


async def _current(db: AsyncSession) -> OperationCertification:
    db.expire_all()
    return (
        await db.execute(
            select(OperationCertification)
            .where(OperationCertification.agentId == "a-1")
            .order_by(OperationCertification.createdAt.desc())
            .limit(1)
        )
    ).scalar_one()


# --- the rule ------------------------------------------------------------------------------------


def test_a_majority_of_up_to_the_last_three_graded_sittings_certifies() -> None:
    """Ivan's Option B, his three examples first (lists are newest first)."""
    assert certifies(["PASS"])  # one sitting, a PASS
    assert not certifies(["PASS", "FAIL"])  # F,P
    assert certifies(["PASS", "PASS", "FAIL"])  # F,P,P
    assert not certifies([])
    assert not certifies(["FAIL"])
    assert not certifies(["FAIL", "PASS"])  # P,F: a tie is not a majority
    assert certifies(["PASS", "PASS"])
    assert not certifies(["FAIL", "PASS", "FAIL"])
    # Only the last three graded count: two old passes behind two fails do not certify.
    assert not certifies(["FAIL", "FAIL", "PASS", "PASS"])
    # An ungraded sitting is skipped, not counted as a fail.
    assert certifies(["TIMEOUT", "PASS", "NOT_RUN"])
    assert not certifies(["TIMEOUT", "NOT_RUN", "PROVISIONAL"])


# --- a re-sit is a new sitting on the same reference ---------------------------------------------


async def test_a_resit_opens_the_next_sitting_and_keeps_every_earlier_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _start(client)
    assert await _close(client, passed=False) == "failed"
    assert await _resit(client) == 2
    assert await _resit(client) == 3

    runs = await _runs(db_session)
    assert [r.sitting for r in runs] == [1, 2, 3]
    assert runs[0].verdict == "FAIL" and runs[0].sittingVerdict == "FAIL"
    assert [r.verdict for r in runs[1:]] == [None, None]
    # The same exam: same agent, module, instructions and rubric.
    assert {(r.agentId, r.moduleId, r.instructionContentHash, r.rubricVersion) for r in runs} == {
        (runs[0].agentId, runs[0].moduleId, runs[0].instructionContentHash, runs[0].rubricVersion)
    }
    # The latest sitting answers for the ref, and it is open.
    assert await _standing(client) == "IN_PROGRESS"


async def test_run_start_never_opens_a_resit(client: AsyncClient, db_session: AsyncSession) -> None:
    await _start(client)
    res = await client.post("/api/operation/run/start", json=START)
    assert res.json()["already_open"] is True
    assert len(await _runs(db_session)) == 1


async def test_a_resit_of_an_exam_never_opened_is_a_404(client: AsyncClient) -> None:
    res = await client.post("/api/operation/run/resit", json={"run_ref": "op-never-opened"})
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "unknown_run_ref"


# --- ADR-0164: a re-sit is refused once the rubric has moved -------------------------------------


async def test_a_resit_is_refused_when_the_rubric_has_moved(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Ivan, 31 Oct. The re-sit would copy 0.13.0 and be graded under the rubric in force: a row
    labelled with a rule that did not decide it. Refused, and the refusal names the way forward."""
    res = await client.post("/api/operation/run/start", json={**START, "rubric_version": "0.13.0"})
    assert res.status_code == 200, res.text

    res = await client.post("/api/operation/run/resit", json={"run_ref": RUN_REF})

    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["error"] == "rubric_moved"
    assert detail["rubric_of_the_exam"] == "0.13.0"
    assert detail["rubric_in_force"] == OPERATION_RUBRIC_VERSION
    assert "new exam" in detail["detail"]
    assert "run/start" in detail["detail"]
    # Nothing was opened, and the sitting it would have copied is untouched.
    runs = await _runs(db_session)
    assert [(r.sitting, r.rubricVersion) for r in runs] == [(1, "0.13.0")]


async def test_a_resit_under_the_rubric_in_force_still_opens(client: AsyncClient) -> None:
    res = await client.post(
        "/api/operation/run/start", json={**START, "rubric_version": OPERATION_RUBRIC_VERSION}
    )
    assert res.status_code == 200, res.text
    assert await _resit(client) == 2


async def test_the_service_refuses_it_too(client: AsyncClient, db_session: AsyncSession) -> None:
    """`scripts/open_resit.py` calls the service, not the route: the rule lives in the service."""
    res = await client.post("/api/operation/run/start", json={**START, "rubric_version": "0.13.0"})
    assert res.status_code == 200, res.text
    with pytest.raises(RubricMoved) as refused:
        await open_resit(db_session, RUN_REF)
    assert (refused.value.was, refused.value.now) == ("0.13.0", OPERATION_RUBRIC_VERSION)
    assert len(await _runs(db_session)) == 1


# --- certification is a majority -----------------------------------------------------------------


async def test_one_sitting_a_pass_is_certified(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _start(client)
    assert await _close(client, passed=True) == "certified"
    assert await _standing(client) == "PASS"
    run = (await _runs(db_session))[0]
    assert (run.sittingVerdict, run.verdict) == ("PASS", "PASS")


async def test_a_pass_after_a_fail_is_held_at_provisional_and_says_why(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """F,P: no majority."""
    await _start(client)
    await _close(client, passed=False)
    await _resit(client)
    assert await _close(client, passed=True) == "provisional"
    cert = await _current(db_session)
    assert cert.state == "provisional"
    assert WITHHOLD_SITTINGS in (cert.withheldBecause or [])
    assert cert.maxCertifiedTrustTier is None
    run = (await _runs(db_session))[1]
    # The sitting passed; the ref does not stand certified.
    assert run.sittingVerdict == "PASS"
    assert run.verdict == "PROVISIONAL"
    assert await _standing(client) == "PROVISIONAL"


async def test_a_fail_after_a_single_pass_loses_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """P,F: a tie is not a majority."""
    await _start(client)
    assert await _close(client, passed=True) == "certified"
    await _resit(client)
    assert await _close(client, passed=False) == "failed"
    assert (await _current(db_session)).state == "failed"


async def test_victors_case_a_fail_then_two_passes_certifies(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Sitting 1 failed (comp_analysis 0.800). Two re-sits opened together, both pass."""
    await _start(client)
    assert await _close(client, passed=False) == "failed"
    two, three = await _resit(client), await _resit(client)
    assert await _close(client, passed=True, sitting=two) == "provisional"
    assert await _close(client, passed=True, sitting=three) == "certified"
    assert await _standing(client) == "PASS"
    assert (await _current(db_session)).state == "certified"
    runs = await _runs(db_session)
    assert [r.sittingVerdict for r in runs] == ["FAIL", "PASS", "PASS"]


async def test_an_unnamed_result_closes_the_oldest_open_sitting(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _start(client)
    await _close(client, passed=False)
    await _resit(client)
    await _resit(client)
    await _close(client, passed=True)
    runs = await _runs(db_session)
    assert [r.sittingVerdict for r in runs] == ["FAIL", "PASS", None]


# --- and is lost the same way --------------------------------------------------------------------


async def test_one_fail_under_two_passes_keeps_the_certification_and_keeps_the_fail(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _start(client)
    assert await _close(client, passed=True) == "certified"
    await _resit(client)
    assert await _close(client, passed=True) == "certified"
    await _resit(client)
    assert await _close(client, passed=False) == "certified"

    assert await _standing(client) == "PASS"
    assert (await _current(db_session)).state == "certified"
    runs = await _runs(db_session)
    assert [r.sittingVerdict for r in runs] == ["PASS", "PASS", "FAIL"]
    # The failed sitting's own row is written, beside the certification it did not lose.
    db_session.expire_all()
    states = [
        c.state
        for c in (
            await db_session.execute(
                select(OperationCertification).order_by(OperationCertification.createdAt)
            )
        )
        .scalars()
        .all()
    ]
    assert states == ["certified", "certified", "failed", "certified"]


async def test_two_fails_in_the_last_three_lose_the_certification(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _start(client)
    await _close(client, passed=True)
    await _resit(client)
    await _close(client, passed=True)
    await _resit(client)
    await _close(client, passed=False)
    await _resit(client)
    assert await _close(client, passed=False) == "failed"
    assert await _standing(client) == "FAIL"
    assert (await _current(db_session)).state == "failed"


async def test_a_certification_revoked_since_is_not_held_up_by_older_passes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _start(client)
    await _close(client, passed=True)
    await _resit(client)
    await _close(client, passed=True)
    cert = await _current(db_session)
    cert.state = "revoked"
    await db_session.commit()

    await _resit(client)
    assert await _close(client, passed=False) == "failed"
    assert (await _current(db_session)).state == "failed"


async def test_a_gate_result_with_no_ref_is_a_first_sitting(client: AsyncClient) -> None:
    """One sitting, a PASS: certified."""
    res = await client.post(
        "/api/operation/gate-result",
        json={
            "instruction_set_ref": REF,
            "run_content_hash": "sha256:si",
            "agent_outcomes": [_outcome()],
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["agent_operation_certs"][0]["state"] == "certified"

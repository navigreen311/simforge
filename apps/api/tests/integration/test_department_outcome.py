"""ADR-0161 - The Office posts a Unit B outcome through the bridge, and it is recorded.

What these hold:

1. A post writes the `department_context` certification and closes the run.
2. The reply is exactly four keys: run_ref, accepted, recorded, status.
3. Agent outcomes are refused, and nothing is written but the audit row.
4. It is idempotent on the key: a retry is answered from the first call and writes no second
   certification; the same key with another payload is refused.
5. A flag not verified gives `provisional`, never `failed` (ADR-0062 option A; ruling of
   23 October 2026). `passed: false` - a recorded defect - gives `failed`.
6. Only The Office's own Unit B run, under its venture, with a key. Every call is audited.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.department_outcome import DepartmentOutcomePost
from src.models.operation_cert import OperationCertification
from src.models.operation_run import OperationRun
from src.routers.office import MODULES
from src.services.operation.department_outcome import (
    REFUSED_ALREADY_CLOSED,
    REFUSED_ANOTHER_VENTURE,
    REFUSED_KEY_REUSED,
    REFUSED_NO_IDEMPOTENCY_KEY,
    REFUSED_NOT_UNIT_B,
    REFUSED_OUTCOME_MISMATCH,
    REFUSED_PAYLOAD_INVALID,
    REFUSED_UNKNOWN_RUN,
)
from src.services.operation.run_registry import gate_result_for, open_run
from tests.integration.test_gate_9_5_verdict import AUTH, bridged  # noqa: F401 - fixture

pytestmark = pytest.mark.asyncio

VENTURE = "greenstone"
FORGE = "cre-forge"
DEPARTMENT = "operations"
BASIS = "2fb5516cab73" + "0" * 52
RUN_REF = f"office:{VENTURE}:{FORGE}:dept:{DEPARTMENT}:2fb5516cab73:p11.0.0:r0.13.0"
UNIT_A_REF = f"office:{VENTURE}:{FORGE}:buyer_match@ronan:264e47be:p11.0.0:r0.13.0"
URL = "/office/department_outcome"
REPLY_KEYS = {"run_ref", "accepted", "recorded", "status"}


async def _open(session: AsyncSession, run_ref: str = RUN_REF, unit: str = "B") -> None:
    await open_run(
        session,
        run_ref=run_ref,
        unit=unit,
        forge_id=FORGE,
        instruction_content_hash=BASIS,
        rubric_kind="domain" if unit == "B" else "operation",
        rubric_version="0.13.0",
        module_id=None if unit == "B" else "buyer_match",
        agent_id=None if unit == "B" else "ronan_valek",
        department_id=DEPARTMENT if unit == "B" else None,
        scenario_count=15,
        coverage_denominator=5,
    )
    await session.commit()


def _payload(
    *,
    run_ref: str = RUN_REF,
    passed: bool = True,
    escalation: bool = True,
    compliance: bool = True,
    **over: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "run_ref": run_ref,
        "instruction_version": "1.11.9",
        "forge_api_version": "1.4.0",
        "department_outcomes": [
            {
                "department_id": DEPARTMENT,
                "forge_id": FORGE,
                "passed": passed,
                "escalation_path_verified": escalation,
                "compliance_coupling_verified": compliance,
            }
        ],
    }
    body.update(over)
    return body


def _headers(key: str | None = "key-1", venture: str | None = VENTURE) -> dict[str, str]:
    headers = dict(AUTH)
    if key is not None:
        headers["Idempotency-Key"] = key
    if venture is not None:
        headers["X-Office-Venture"] = venture
    return headers


async def _dept_certs(session: AsyncSession) -> list[OperationCertification]:
    return list(
        (
            await session.execute(
                select(OperationCertification).where(
                    OperationCertification.unitType == "department_context"
                )
            )
        )
        .scalars()
        .all()
    )


async def _audit(session: AsyncSession) -> list[DepartmentOutcomePost]:
    return list(
        (await session.execute(select(DepartmentOutcomePost).order_by(DepartmentOutcomePost.at)))
        .scalars()
        .all()
    )


# --- 1. it writes the certification ---------------------------------------------------------


async def test_a_post_writes_the_department_certification_and_closes_the_run(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session)

    res = await bridged.post(URL, json=_payload(), headers=_headers())

    assert res.status_code == 200, res.text
    certs = await _dept_certs(db_session)
    assert len(certs) == 1
    cert = certs[0]
    assert cert.state == "certified"
    assert cert.departmentId == DEPARTMENT
    assert cert.forgeId == FORGE
    assert cert.instructionContentHash == BASIS
    assert cert.escalationPathVerified is True
    assert cert.complianceCouplingVerified is True
    # The run is closed with the verdict The Office reads back on the ordinary path.
    body = await gate_result_for(db_session, RUN_REF)
    assert body is not None
    assert body["verdict"] == "PASS"


async def test_an_outcome_arriving_after_the_timeout_is_still_recorded(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session)
    run = (
        await db_session.execute(select(OperationRun).where(OperationRun.runRef == RUN_REF))
    ).scalar_one()
    run.verdict = "TIMEOUT"
    await db_session.commit()

    res = await bridged.post(URL, json=_payload(), headers=_headers())

    assert res.status_code == 200, res.text
    assert [c.state for c in await _dept_certs(db_session)] == ["certified"]


# --- 2. the reply is four keys --------------------------------------------------------------


async def test_the_reply_is_the_four_keys_and_nothing_else(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session)

    res = await bridged.post(URL, json=_payload(), headers=_headers())

    assert res.status_code == 200
    body = res.json()
    assert set(body) == REPLY_KEYS
    assert body == {"run_ref": RUN_REF, "accepted": True, "recorded": 1, "status": "recorded"}
    # No verdict on the wire: it travels back through gate_result like every other verdict.
    assert "verdict" not in res.text and "certified" not in res.text
    assert res.headers.get("X-Forge-Request-Id")


# --- 3. agent outcomes are refused ----------------------------------------------------------


async def test_agent_outcomes_are_refused_and_nothing_is_written(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session)
    payload = _payload(agent_outcomes=[{"agent_id": "ronan_valek", "module_id": "buyer_match"}])

    res = await bridged.post(URL, json=payload, headers=_headers())

    assert res.status_code == 422
    assert res.json()["detail"]["error"] == REFUSED_PAYLOAD_INVALID
    assert await _dept_certs(db_session) == []
    count = await db_session.execute(select(func.count()).select_from(OperationCertification))
    assert count.scalar_one() == 0
    run = (
        await db_session.execute(select(OperationRun).where(OperationRun.runRef == RUN_REF))
    ).scalar_one()
    assert run.verdict is None
    [row] = await _audit(db_session)
    assert (row.outcome, row.refusal) == ("refused", REFUSED_PAYLOAD_INVALID)


async def test_a_unit_a_run_is_refused(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session, run_ref=UNIT_A_REF, unit="A")

    res = await bridged.post(URL, json=_payload(run_ref=UNIT_A_REF), headers=_headers())

    assert res.status_code == 422
    assert res.json()["detail"]["error"] == REFUSED_NOT_UNIT_B
    assert await _dept_certs(db_session) == []


async def test_an_outcome_for_another_department_is_refused(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session)
    payload = _payload()
    payload["department_outcomes"][0]["department_id"] = "research"

    res = await bridged.post(URL, json=payload, headers=_headers())

    assert res.status_code == 422
    assert res.json()["detail"]["error"] == REFUSED_OUTCOME_MISMATCH
    assert await _dept_certs(db_session) == []


# --- 4. idempotent on the key ---------------------------------------------------------------


async def test_a_retry_with_the_same_key_is_answered_and_writes_nothing_more(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session)

    first = await bridged.post(URL, json=_payload(), headers=_headers("key-retry"))
    second = await bridged.post(URL, json=_payload(), headers=_headers("key-retry"))

    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == "recorded"
    assert second.json() == {
        "run_ref": RUN_REF,
        "accepted": True,
        "recorded": 1,
        "status": "replayed",
    }
    assert len(await _dept_certs(db_session)) == 1
    assert [r.outcome for r in await _audit(db_session)] == ["recorded", "replayed"]


async def test_the_same_key_with_another_payload_is_refused(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session)
    await bridged.post(URL, json=_payload(), headers=_headers("key-x"))

    res = await bridged.post(URL, json=_payload(compliance=False), headers=_headers("key-x"))

    assert res.status_code == 409
    assert res.json()["detail"]["error"] == REFUSED_KEY_REUSED
    assert [c.state for c in await _dept_certs(db_session)] == ["certified"]


async def test_a_second_post_with_a_new_key_on_a_closed_run_is_refused(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session)
    await bridged.post(URL, json=_payload(), headers=_headers("key-a"))

    res = await bridged.post(URL, json=_payload(), headers=_headers("key-b"))

    assert res.status_code == 409
    assert res.json()["detail"]["error"] == REFUSED_ALREADY_CLOSED
    assert len(await _dept_certs(db_session)) == 1


async def test_a_post_without_a_key_is_refused(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session)

    res = await bridged.post(URL, json=_payload(), headers=_headers(key=None))

    assert res.status_code == 422
    assert res.json()["detail"]["error"] == REFUSED_NO_IDEMPOTENCY_KEY
    assert await _dept_certs(db_session) == []


# --- 5. the states ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("escalation", "compliance"),
    [(True, False), (False, True), (False, False)],
)
async def test_a_flag_not_verified_gives_provisional(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
    escalation: bool,
    compliance: bool,
) -> None:
    await _open(db_session)

    res = await bridged.post(
        URL, json=_payload(escalation=escalation, compliance=compliance), headers=_headers()
    )

    assert res.status_code == 200, res.text
    assert [c.state for c in await _dept_certs(db_session)] == ["provisional"]
    body = await gate_result_for(db_session, RUN_REF)
    assert body is not None
    assert body["verdict"] == "PROVISIONAL"


async def test_a_recorded_defect_gives_failed(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session)

    res = await bridged.post(URL, json=_payload(passed=False), headers=_headers())

    assert res.status_code == 200, res.text
    assert [c.state for c in await _dept_certs(db_session)] == ["failed"]


# --- 6. who may post, and the audit ---------------------------------------------------------


@pytest.mark.parametrize(
    ("run_ref", "venture", "code"),
    [
        (RUN_REF, "burkham-wickmont", REFUSED_ANOTHER_VENTURE),
        (RUN_REF.replace("2fb5516cab73", "000000000000"), VENTURE, REFUSED_UNKNOWN_RUN),
    ],
)
async def test_every_lookup_refusal_is_the_same_404_and_is_audited(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
    run_ref: str,
    venture: str,
    code: str,
) -> None:
    await _open(db_session)

    res = await bridged.post(URL, json=_payload(run_ref=run_ref), headers=_headers(venture=venture))

    assert res.status_code == 404
    assert res.json()["detail"] == (
        "SimForge holds no department run The Office may post an outcome for"
    )
    assert await _dept_certs(db_session) == []
    [row] = await _audit(db_session)
    assert (row.outcome, row.refusal, row.officeVenture) == ("refused", code, venture)


async def test_a_retry_under_another_venture_is_refused_before_it_is_replayed(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session)
    await bridged.post(URL, json=_payload(), headers=_headers("key-v"))

    res = await bridged.post(
        URL, json=_payload(), headers=_headers("key-v", venture="burkham-wickmont")
    )

    assert res.status_code == 404
    assert [r.outcome for r in await _audit(db_session)] == ["recorded", "refused"]


async def test_the_recorded_audit_row_carries_the_call(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _open(db_session)
    headers = {**_headers("key-audit"), "X-Office-Trace": "trace-7"}

    res = await bridged.post(URL, json=_payload(), headers=headers)

    [row] = await _audit(db_session)
    assert row.outcome == "recorded"
    assert row.runRef == RUN_REF
    assert row.officeVenture == VENTURE
    assert row.officeTrace == "trace-7"
    assert row.idempotencyKey == "key-audit"
    assert row.payloadDigest
    assert row.recorded == 1
    assert row.forgeRequestId == res.headers["X-Forge-Request-Id"]


async def test_the_module_is_declared_a_keyed_writer() -> None:
    spec = MODULES["department_outcome"]
    assert spec.is_mutating is True
    assert spec.idempotency_support == "key"

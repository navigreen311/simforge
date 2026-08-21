"""Batch 5 — gating requires BOTH a current Unit A and a current Unit B; B is necessary but not
sufficient; a new agent in a certified department is never_certified until it earns A."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_cert import OperationCertification
from src.services.operation.gating import (
    agent_module_assignability,
    module_has_any_certified_agent,
)
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION


def _unit_a(agent: str, state: str = "certified") -> OperationCertification:
    return OperationCertification(
        unitType="agent_operation",
        state=state,
        forgeId="medlink-pro",
        instructionVersion="1.4.0",
        forgeApiVersion="2.1.3",
        instructionContentHash="h",
        operationRubricVersion=OPERATION_RUBRIC_VERSION,
        agentId=agent,
        moduleId="statement_ingest",
        functionsCertified=11,
        functionsInModule=14,
    )


def _unit_b(state: str = "certified") -> OperationCertification:
    return OperationCertification(
        unitType="department_context",
        state=state,
        forgeId="medlink-pro",
        instructionVersion="1.4.0",
        forgeApiVersion="2.1.3",
        instructionContentHash="h",
        operationRubricVersion=OPERATION_RUBRIC_VERSION,
        departmentId="Engineering",  # gating matches Department.villageKey or id
        forgeContext="facility_console",
        ventureContext="medlink",
        escalationPathVerified=True,
        complianceCouplingVerified=True,
    )


async def test_unit_a_without_unit_b_is_not_assignable(db_session: AsyncSession) -> None:
    db_session.add(_unit_a("taylor_zhang"))
    await db_session.commit()
    res = await agent_module_assignability(
        db_session, agent_id="taylor_zhang", module_id="statement_ingest", venture_context="medlink"
    )
    assert res.assignable is False
    assert res.unit_a_state == "certified"
    assert res.unit_b_state == "never_certified"
    assert "Unit B" in res.reason


async def test_both_units_current_is_assignable(db_session: AsyncSession) -> None:
    db_session.add_all([_unit_a("taylor_zhang"), _unit_b()])
    await db_session.commit()
    res = await agent_module_assignability(
        db_session, agent_id="taylor_zhang", module_id="statement_ingest", venture_context="medlink"
    )
    assert res.assignable is True
    assert res.unit_a_state == "certified" and res.unit_b_state == "certified"


async def test_new_agent_in_certified_dept_is_never_certified_until_earns_a(
    db_session: AsyncSession,
) -> None:
    # Department has a Unit B (context cleared) but david_kim has no Unit A → not assignable.
    db_session.add(_unit_b())
    await db_session.commit()
    res = await agent_module_assignability(
        db_session,
        agent_id="david_kim",
        module_id="statement_ingest",
        venture_context="medlink",
        forge_id="medlink-pro",  # the shift context names the forge (agent has no Unit A yet)
    )
    assert res.assignable is False
    assert res.unit_a_state == "never_certified"  # a real absence, not a failure
    assert res.unit_b_state == "certified"  # B necessary but not sufficient


async def test_failed_unit_a_is_distinct_from_never_certified(db_session: AsyncSession) -> None:
    db_session.add_all([_unit_a("taylor_zhang", state="failed"), _unit_b()])
    await db_session.commit()
    res = await agent_module_assignability(
        db_session, agent_id="taylor_zhang", module_id="statement_ingest", venture_context="medlink"
    )
    assert res.assignable is False
    assert res.unit_a_state == "failed"  # ran and did not pass — NOT never_certified


async def test_module_has_any_certified_agent_reporting_helper(db_session: AsyncSession) -> None:
    assert (
        await module_has_any_certified_agent(
            db_session, forge_id="medlink-pro", module_id="statement_ingest"
        )
        is False
    )
    db_session.add(_unit_a("taylor_zhang"))
    await db_session.commit()
    assert (
        await module_has_any_certified_agent(
            db_session, forge_id="medlink-pro", module_id="statement_ingest"
        )
        is True
    )

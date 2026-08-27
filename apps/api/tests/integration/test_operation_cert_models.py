"""Forge Operation Certification data model (Batch 2): both unit types persist; the 7 states are
distinct and store as themselves; operation_rubric_version is carried and SEPARATE from domain."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.operation_cert import OperationCertification
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION
from src.services.operation.state_machine import OPERATION_STATES


async def test_forge_instruction_set_persists(db_session: AsyncSession) -> None:
    iset = ForgeInstructionSet(
        forgeId="medlink-pro",
        moduleId="statement_ingest",
        instructionVersion="1.4.0",
        forgeApiVersion="2.1.3",
        authoredBy="ivan",
        contentHash="sha256:abc123",
    )
    db_session.add(iset)
    await db_session.commit()

    row = (
        await db_session.execute(
            select(ForgeInstructionSet).where(ForgeInstructionSet.moduleId == "statement_ingest")
        )
    ).scalar_one()
    assert row.forgeApiVersion == "2.1.3"
    assert row.contentHash == "sha256:abc123"


async def test_unit_a_agent_operation_persists_with_denominator(db_session: AsyncSession) -> None:
    cert = OperationCertification(
        unitType="agent_operation",
        state="certified",
        forgeId="medlink-pro",
        instructionVersion="1.4.0",
        forgeApiVersion="2.1.3",
        instructionContentHash="sha256:abc123",
        operationRubricVersion=OPERATION_RUBRIC_VERSION,
        agentId="taylor_zhang",
        moduleId="statement_ingest",
        functionsCertified=11,
        functionsInModule=14,  # DENOMINATOR carried
        maxCertifiedTrustTier="propose",
        perScenarioClass={"happy_path": "PASS", "never_do_violation": "PASS"},
        operationRubricResults=[
            {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.95},
            {"dimension": "never_do_adherence", "verdict": "not_applicable"},
        ],
        rubricDimensionSpread=0.0,
        failureModesObserved=[],
        versionSensitivity={"statement_ingest": ["major", "minor"]},
    )
    db_session.add(cert)
    await db_session.commit()

    row = (
        await db_session.execute(
            select(OperationCertification).where(
                OperationCertification.agentId == "taylor_zhang"
            )
        )
    ).scalar_one()
    assert row.functionsCertified == 11
    assert row.functionsInModule == 14
    assert row.maxCertifiedTrustTier == "propose"
    # not_applicable persisted as a first-class verdict, not a zero score.
    na = [r for r in row.operationRubricResults if r["dimension"] == "never_do_adherence"][0]
    assert na["verdict"] == "not_applicable"
    assert "score" not in na
    # operation_rubric_version is present and NOT the domain rubric_version.
    assert row.operationRubricVersion == OPERATION_RUBRIC_VERSION
    # Unit B fields are cleanly null on a Unit A row.
    assert row.departmentId is None
    assert row.escalationPathVerified is None


async def test_unit_b_department_context_persists(db_session: AsyncSession) -> None:
    cert = OperationCertification(
        unitType="department_context",
        state="certified",
        forgeId="medlink-pro",
        instructionVersion="1.4.0",
        forgeApiVersion="2.1.3",
        instructionContentHash="sha256:abc123",
        operationRubricVersion=OPERATION_RUBRIC_VERSION,
        departmentId="clinical_ops",
        forgeContext="facility_console",
        ventureContext="medlink",
        escalationPathVerified=True,
        complianceCouplingVerified=True,
    )
    db_session.add(cert)
    await db_session.commit()

    row = (
        await db_session.execute(
            select(OperationCertification).where(
                OperationCertification.departmentId == "clinical_ops"
            )
        )
    ).scalar_one()
    assert row.escalationPathVerified is True
    assert row.complianceCouplingVerified is True
    # Unit A fields cleanly null on a Unit B row.
    assert row.agentId is None
    assert row.functionsInModule is None


async def test_operation_states_are_distinct_and_round_trip(db_session: AsyncSession) -> None:
    # 8 states after the Rev-2 audit added `provisional` (a passed-but-withheld hold, distinct from
    # both certified and failed). Each persists as itself — never collapsed, never a low score.
    assert len(OPERATION_STATES) == 8
    assert len(set(OPERATION_STATES)) == 8
    assert "provisional" in OPERATION_STATES
    for state in OPERATION_STATES:
        db_session.add(
            OperationCertification(
                unitType="agent_operation",
                state=state,
                forgeId="f",
                instructionVersion="1.0.0",
                forgeApiVersion="1.0.0",
                instructionContentHash="h",
                operationRubricVersion=OPERATION_RUBRIC_VERSION,
                agentId=f"agent_{state}",
                moduleId="m",
                functionsCertified=0,
                functionsInModule=3,
            )
        )
    await db_session.commit()

    rows = (
        await db_session.execute(
            select(OperationCertification).where(OperationCertification.moduleId == "m")
        )
    ).scalars().all()
    stored = {r.state for r in rows}
    # never_certified and failed persist as themselves — never collapsed, never a low score.
    assert stored == set(OPERATION_STATES)
    assert "never_certified" in stored
    assert "failed" in stored

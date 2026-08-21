"""Batch 4/5 — the content-hash VOID rule (revoked + HIGH incident) and every re-cert trigger,
each landing on a DISTINCT state; version_sensitivity governs patch invalidation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.gap import SoftwareGap
from src.models.operation_cert import OperationCertification
from src.services.operation.recert import (
    changed_component,
    mark_never_certified_for_new_agent,
    mark_stale_on_forge_change,
    mark_stale_on_instruction_change,
    recert_on_operation_rubric_change,
    revoke_on_incident,
    revoke_on_runtime_drift,
    void_certification,
)
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION


def _cert(**over) -> OperationCertification:
    base = dict(
        unitType="agent_operation",
        state="certified",
        forgeId="medlink-pro",
        instructionVersion="1.4.0",
        forgeApiVersion="2.1.3",
        instructionContentHash="sha256:declared",
        operationRubricVersion=OPERATION_RUBRIC_VERSION,
        agentId="taylor_zhang",
        moduleId="statement_ingest",
        functionsCertified=11,
        functionsInModule=14,
    )
    base.update(over)
    return OperationCertification(**base)


# --- content-hash VOID ---------------------------------------------------------------------------


async def test_content_hash_mismatch_voids_to_revoked_and_raises_high_incident(
    db_session: AsyncSession,
) -> None:
    cert = _cert()
    db_session.add(cert)
    await db_session.commit()

    voided = await void_certification(
        db_session,
        cert=cert,
        declared_hash="sha256:declared",
        run_hash="sha256:TAMPERED",
        run_ref="run-void-1",
    )
    assert voided is True
    assert cert.state == "revoked"  # VOID, never a warning

    gaps = (
        (await db_session.execute(select(SoftwareGap).where(SoftwareGap.severity == "P0")))
        .scalars()
        .all()
    )
    assert len(gaps) == 1  # HIGH-severity incident raised via the existing gap mechanism
    assert gaps[0].status == "open"
    # An operation VOID is not a scenario Run — the gap must carry NO runId FK (real Postgres
    # enforces it; the hermetic SQLite run does not, so this assertion guards the regression).
    assert gaps[0].runId is None
    assert gaps[0].firstSeenRunId == "run-void-1"


async def test_matching_hash_does_not_void(db_session: AsyncSession) -> None:
    cert = _cert()
    db_session.add(cert)
    await db_session.commit()
    voided = await void_certification(
        db_session, cert=cert, declared_hash="sha256:declared", run_hash="sha256:declared"
    )
    assert voided is False
    assert cert.state == "certified"


async def test_gate_result_void_path_via_router(client) -> None:  # noqa: ANN001
    payload = {
        "instruction_set_ref": {
            "forge_id": "medlink-pro",
            "module_id": "statement_ingest",
            "instruction_version": "1.4.0",
            "forge_api_version": "2.1.3",
            "content_hash": "sha256:declared",
        },
        "run_content_hash": "sha256:TAMPERED",  # mismatch → VOID
        "run_ref": "run-router-void",
        "agent_outcomes": [
            {
                "agent_id": "taylor_zhang",
                "module_id": "statement_ingest",
                "forge_id": "medlink-pro",
                "functions_certified": 11,
                "functions_in_module": 14,
                "passed": True,
                "operation_rubric_results": [
                    {"dimension": "sequence_correctness", "verdict": "PASS", "score": 0.9}
                ],
            }
        ],
    }
    out = (await client.post("/api/operation/gate-result", json=payload)).json()
    assert out["agent_operation_certs"][0]["state"] == "revoked"  # not certified despite passed
    incident = (await client.get("/api/incident/status")).json()
    assert incident["counts"]["high"] >= 1


# --- stale triggers ------------------------------------------------------------------------------


async def test_instruction_version_change_marks_stale_instructions(
    db_session: AsyncSession,
) -> None:
    db_session.add(_cert(instructionVersion="1.4.0"))
    await db_session.commit()
    affected = await mark_stale_on_instruction_change(
        db_session,
        forge_id="medlink-pro",
        module_id="statement_ingest",
        new_instruction_version="1.5.0",
    )
    assert len(affected) == 1
    assert affected[0].state == "stale_instructions"


async def test_forge_major_change_marks_stale_forge(db_session: AsyncSession) -> None:
    db_session.add(_cert(forgeApiVersion="2.1.3"))
    await db_session.commit()
    affected = await mark_stale_on_forge_change(
        db_session,
        forge_id="medlink-pro",
        module_id="statement_ingest",
        new_forge_api_version="3.0.0",
    )
    assert len(affected) == 1
    assert affected[0].state == "stale_forge"


async def test_forge_patch_change_does_not_invalidate_unless_declared(
    db_session: AsyncSession,
) -> None:
    # No patch-sensitivity declared → a patch bump does NOT invalidate (Rev 2 Q4).
    db_session.add(
        _cert(
            forgeApiVersion="2.1.3",
            versionSensitivity={"statement_ingest": ["major", "minor"]},
        )
    )
    # A patch-sensitive cert → a patch bump DOES invalidate.
    db_session.add(
        _cert(
            agentId="david_kim",
            forgeApiVersion="2.1.3",
            versionSensitivity={"statement_ingest": ["patch"]},
        )
    )
    await db_session.commit()
    affected = await mark_stale_on_forge_change(
        db_session,
        forge_id="medlink-pro",
        module_id="statement_ingest",
        new_forge_api_version="2.1.4",
    )
    agents = {c.agentId for c in affected}
    assert agents == {"david_kim"}


def test_changed_component_semver_diff() -> None:
    assert changed_component("2.1.3", "3.0.0") == "major"
    assert changed_component("2.1.3", "2.2.0") == "minor"
    assert changed_component("2.1.3", "2.1.4") == "patch"
    assert changed_component("2.1.3", "2.1.3") is None


# --- never_certified / drift / incident / rubric -------------------------------------------------


async def test_new_agent_gets_never_certified_rows(db_session: AsyncSession) -> None:
    created = await mark_never_certified_for_new_agent(
        db_session,
        agent_id="new_hire",
        forge_id="medlink-pro",
        modules=["statement_ingest", "billing"],
    )
    assert len(created) == 2
    assert all(c.state == "never_certified" for c in created)
    assert all(c.functionsInModule is None for c in created)  # unknown until a battery runs


async def test_runtime_drift_revokes_with_remediation(db_session: AsyncSession) -> None:
    db_session.add(_cert())
    await db_session.commit()
    affected = await revoke_on_runtime_drift(
        db_session, agent_id="taylor_zhang", module_id="statement_ingest"
    )
    assert len(affected) == 1
    assert affected[0].state == "revoked"
    assert any("remediation" in m for m in affected[0].failureModesObserved)


async def test_incident_revokes_both_units(db_session: AsyncSession) -> None:
    db_session.add(_cert(agentId="taylor_zhang"))
    db_session.add(
        _cert(
            unitType="department_context",
            agentId=None,
            moduleId=None,
            functionsCertified=None,
            functionsInModule=None,
            departmentId="Engineering",
            ventureContext="medlink",
        )
    )
    await db_session.commit()
    affected = await revoke_on_incident(
        db_session, agent_id="taylor_zhang", department_id="Engineering", forge_id="medlink-pro"
    )
    assert len(affected) == 2  # BOTH units
    assert all(c.state == "revoked" for c in affected)


async def test_operation_rubric_change_recerts_operation_unit_only(
    db_session: AsyncSession,
) -> None:
    db_session.add(_cert(operationRubricVersion="0.0.1"))  # earned under a prior rubric version
    await db_session.commit()
    affected = await recert_on_operation_rubric_change(
        db_session, new_operation_rubric_version=OPERATION_RUBRIC_VERSION
    )
    assert len(affected) == 1
    # Re-cert required (not assignable), operation unit only — the domain cert table is untouched.
    assert affected[0].state == "stale_instructions"

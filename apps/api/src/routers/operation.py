"""Forge Operation Certification router (Batches 3-5).

Endpoints:
  POST /api/operation/curriculum         — submit a curriculum; validate + reject Batch-3 violations
  POST /api/operation/gate-result        — an operation battery's outcome → persist + Batch-4 echo
                                           (content-hash VOID → revoked + HIGH incident)
  GET  /api/operation/agents/{agent_id}  — per-agent operation cert state (module, state, versions)
  GET  /api/operation/coverage/{forge}   — honest coverage denominators for a forge
  GET  /api/operation/assignability      — gating result (Unit A AND Unit B)

Two rubrics, two records, never one number: nothing here merges an operation result with a domain
result, and the domain cert tables are never touched.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.operation_cert import OperationCertification
from src.schemas.operation_payloads import (
    AgentOperationCertResult,
    DepartmentContextCertResult,
    ForgeOperationCurriculum,
    ForgeOperationResults,
    GateResultRequest,
    OperationRubricResultItem,
)
from src.services.operation.gating import (
    agent_module_assignability,
    agent_operation_states,
)
from src.services.operation.recert import is_content_hash_void, raise_high_incident
from src.services.operation.rubric import (
    OPERATION_RUBRIC_VERSION,
    compute_rubric_dimension_spread,
)
from src.services.operation.scenarios import validate_curriculum_submission
from src.services.operation.state_machine import OperationState, is_assignable

router = APIRouter()


# =================================================================================================
# Submit curriculum
# =================================================================================================


@router.post("/curriculum", dependencies=[Depends(require_role("forge_owner"))])
async def submit_curriculum(
    body: ForgeOperationCurriculum, session: AsyncSession = Depends(get_session)
) -> dict:
    """Validate a curriculum submission against the Batch-3 rules. Reject (422) on any violation.
    On success, upsert the bound instruction set and echo per-module cert levels + the Gate 9.5
    flag."""
    scenarios = [s.model_dump() for s in body.operation_scenarios]
    requested_modules = sorted(
        {s.module_id for s in body.operation_scenarios}
        | {u.module_id for u in body.certification_units_requested if u.module_id}
    )
    result = validate_curriculum_submission(
        scenarios,
        module_never_do=body.module_never_do,
        requested_modules=requested_modules or None,
    )
    if result.rejected:
        raise HTTPException(
            status_code=422,  # unprocessable content — curriculum failed Batch-3 validation
            detail={
                "error": "curriculum_rejected",
                "violations": result.violations,
                "gate_9_5_flag": result.gate_9_5_flag,
            },
        )

    ref = body.instruction_set_ref
    existing = (
        await session.execute(
            select(ForgeInstructionSet).where(
                ForgeInstructionSet.forgeId == ref.forge_id,
                ForgeInstructionSet.moduleId == ref.module_id,
                ForgeInstructionSet.contentHash == ref.content_hash,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            ForgeInstructionSet(
                forgeId=ref.forge_id,
                moduleId=ref.module_id,
                instructionVersion=ref.instruction_version,
                forgeApiVersion=ref.forge_api_version,
                authoredBy=ref.authored_by or "office",
                contentHash=ref.content_hash,
            )
        )
        await session.commit()

    return {
        "accepted": True,
        "module_levels": result.module_levels,
        "coverage_declaration": body.coverage_declaration.model_dump(),
        "gate_9_5_flag": result.gate_9_5_flag,
    }


# =================================================================================================
# Gate-result callback (persist outcomes + Batch-4 outbound shape)
# =================================================================================================


def _out_dim(item: OperationRubricResultItem) -> dict:
    d: dict = {"dimension": item.dimension, "verdict": item.verdict}
    if item.score is not None:
        d["score"] = item.score
    if item.threshold is not None:
        d["threshold"] = item.threshold
    return d


@router.post("/gate-result", dependencies=[Depends(require_role("compliance_analyst"))])
async def gate_result(
    body: GateResultRequest, session: AsyncSession = Depends(get_session)
) -> ForgeOperationResults:
    """Persist an operation battery's outcome and echo the Rev 2 outbound shape.

    Content-hash VOID rule: if the run's content_hash != the Office-declared hash, EVERY resulting
    cert is VOID → state `revoked` + a single HIGH-severity incident. Never softened to a warning.
    """
    ref = body.instruction_set_ref
    op_rubric_version = body.operation_rubric_version or OPERATION_RUBRIC_VERSION
    void = is_content_hash_void(ref.content_hash, body.run_content_hash)
    run_ref = body.run_ref or "op-run-unknown"

    if void:
        # One HIGH incident for the whole voided run.
        await raise_high_incident(
            session,
            forge=ref.forge_id,
            module=ref.module_id,
            summary=(
                f"Operation run VOID: instruction content_hash mismatch on "
                f"{ref.forge_id}/{ref.module_id}"
            ),
            detail=(
                f"Run executed against content_hash {body.run_content_hash!r} but The Office "
                f"declared {ref.content_hash!r}. All resulting certs are void (revoked). "
                f"run_ref={run_ref}."
            ),
            run_ref=run_ref,
        )

    agent_results: list[AgentOperationCertResult] = []
    for outcome in body.agent_outcomes:
        results_dicts = [_out_dim(r) for r in outcome.operation_rubric_results]
        spread = compute_rubric_dimension_spread(results_dicts)
        if void:
            state = OperationState.REVOKED.value
        elif outcome.passed:
            state = OperationState.CERTIFIED.value
        else:
            state = OperationState.FAILED.value

        cert = OperationCertification(
            unitType="agent_operation",
            state=state,
            forgeId=outcome.forge_id,
            instructionVersion=ref.instruction_version,
            forgeApiVersion=ref.forge_api_version,
            instructionContentHash=body.run_content_hash,
            operationRubricVersion=op_rubric_version,
            agentId=outcome.agent_id,
            moduleId=outcome.module_id,
            functionsCertified=outcome.functions_certified,
            functionsInModule=outcome.functions_in_module,
            maxCertifiedTrustTier=outcome.max_certified_trust_tier,
            perScenarioClass={
                r.scenario_class: r.verdict for r in outcome.per_scenario_class_results
            },
            operationRubricResults=results_dicts,
            rubricDimensionSpread=spread,
            failureModesObserved=list(outcome.failure_modes_observed),
            versionSensitivity=outcome.version_sensitivity or None,
            expiresAt=outcome.expires_at,
        )
        session.add(cert)
        agent_results.append(
            AgentOperationCertResult(
                agent_id=outcome.agent_id,
                module_id=outcome.module_id,
                forge_id=outcome.forge_id,
                state=state,
                max_certified_trust_tier=outcome.max_certified_trust_tier,
                operation_rubric_results=outcome.operation_rubric_results,
                rubric_dimension_spread=spread,
                per_scenario_class_results=outcome.per_scenario_class_results,
                functions_certified=outcome.functions_certified,
                functions_in_module=outcome.functions_in_module,
                failure_modes_observed=list(outcome.failure_modes_observed),
                expires_at=outcome.expires_at,
            )
        )

    dept_results: list[DepartmentContextCertResult] = []
    for d_outcome in body.department_outcomes:
        if void:
            d_state = OperationState.REVOKED.value
        elif d_outcome.passed:
            d_state = OperationState.CERTIFIED.value
        else:
            d_state = OperationState.FAILED.value
        session.add(
            OperationCertification(
                unitType="department_context",
                state=d_state,
                forgeId=d_outcome.forge_id,
                instructionVersion=ref.instruction_version,
                forgeApiVersion=ref.forge_api_version,
                instructionContentHash=body.run_content_hash,
                operationRubricVersion=op_rubric_version,
                departmentId=d_outcome.department_id,
                forgeContext=d_outcome.forge_context,
                ventureContext=d_outcome.venture_context,
                escalationPathVerified=d_outcome.escalation_path_verified,
                complianceCouplingVerified=d_outcome.compliance_coupling_verified,
            )
        )
        dept_results.append(
            DepartmentContextCertResult(
                department_id=d_outcome.department_id,
                forge_id=d_outcome.forge_id,
                state=d_state,
                escalation_path_verified=d_outcome.escalation_path_verified,
                compliance_coupling_verified=d_outcome.compliance_coupling_verified,
            )
        )

    await session.commit()

    return ForgeOperationResults(
        instruction_version_certified_under=ref.instruction_version,
        forge_api_version_certified_under=ref.forge_api_version,
        instruction_content_hash=body.run_content_hash,  # ECHOED
        operation_rubric_version=op_rubric_version,
        agent_operation_certs=agent_results,
        department_context_certs=dept_results,
        capability_matrix_delta=[],
    )


# =================================================================================================
# Reads
# =================================================================================================


@router.get("/agents/{agent_id}", dependencies=[Depends(require_role("viewer"))])
async def agent_operation_view(
    agent_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    """Per-agent operation view: which modules certified/stale/never, under which versions, with the
    denominator always carried. Never merged with the agent's domain cert."""
    certs = await agent_operation_states(session, agent_id=agent_id)
    return {
        "agent_id": agent_id,
        "operation_rubric_version": OPERATION_RUBRIC_VERSION,
        "modules": [
            {
                "module_id": c.moduleId,
                "forge_id": c.forgeId,
                "state": c.state,
                "assignable": is_assignable(c.state),
                "instruction_version": c.instructionVersion or None,
                "forge_api_version": c.forgeApiVersion or None,
                "operation_rubric_version": c.operationRubricVersion,
                "functions_certified": c.functionsCertified,
                "functions_in_module": c.functionsInModule,  # DENOMINATOR
                "max_certified_trust_tier": c.maxCertifiedTrustTier,
                "rubric_dimension_spread": c.rubricDimensionSpread,
            }
            for c in certs
        ],
    }


@router.get("/coverage/{forge_id}", dependencies=[Depends(require_role("viewer"))])
async def coverage_view(forge_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Honest coverage denominators for a forge, derived from persisted Unit A certs: per module,
    functions_certified of functions_in_module, and how many modules have a current cert."""
    certs = (
        (
            await session.execute(
                select(OperationCertification).where(
                    OperationCertification.unitType == "agent_operation",
                    OperationCertification.forgeId == forge_id,
                )
            )
        )
        .scalars()
        .all()
    )
    per_module: dict[str, dict] = {}
    for c in certs:
        mod = c.moduleId or "unknown"
        entry = per_module.setdefault(
            mod,
            {
                "module_id": mod,
                "functions_in_module": c.functionsInModule,
                "functions_certified": 0,
                "has_current_cert": False,
                "states": [],
            },
        )
        entry["states"].append(c.state)
        if c.functionsInModule is not None:
            entry["functions_in_module"] = c.functionsInModule
        if c.state == OperationState.CERTIFIED.value:
            entry["has_current_cert"] = True
            entry["functions_certified"] = max(
                entry["functions_certified"], c.functionsCertified or 0
            )
    modules = sorted(per_module.values(), key=lambda m: m["module_id"])
    return {
        "forge_id": forge_id,
        "modules_covered": sum(1 for m in modules if m["has_current_cert"]),
        "modules_seen": len(modules),
        "modules": modules,
    }


@router.get("/assignability", dependencies=[Depends(require_role("viewer"))])
async def assignability(
    agent_id: str = Query(...),
    module_id: str = Query(...),
    venture_context: str | None = Query(default=None),
    forge_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Gating: assignable only if the agent holds a current Unit A AND its department holds a
    current Unit B for the module's forge in that venture context. Both required; B necessary not
    sufficient."""
    res = await agent_module_assignability(
        session,
        agent_id=agent_id,
        module_id=module_id,
        venture_context=venture_context,
        forge_id=forge_id,
    )
    return {
        "assignable": res.assignable,
        "agent_id": res.agent_id,
        "module_id": res.module_id,
        "forge_id": res.forge_id,
        "venture_context": res.venture_context,
        "unit_a_state": res.unit_a_state,
        "unit_b_state": res.unit_b_state,
        "reason": res.reason,
    }

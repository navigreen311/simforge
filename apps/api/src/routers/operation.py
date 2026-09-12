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
from src.deps import Principal, get_current_principal, require_role
from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.operation_cert import OperationCertification
from src.models.operation_run import OperationRun
from src.schemas.operation_payloads import (
    AgentOperationCertResult,
    DepartmentContextCertResult,
    ForgeOperationCurriculum,
    ForgeOperationResults,
    GateResultRequest,
    HeldOutInventoryResponse,
    OperationRubricResultItem,
    OperationRunStarted,
    OperationRunStartRequest,
    TimedOutRun,
    TimeoutSweepResult,
)
from src.services.operation.battery_result import battery_result_for
from src.services.operation.gating import (
    agent_module_assignability,
    agent_operation_states,
)
from src.services.operation.held_out import (
    HELD_OUT_CONTENT_REFUSED,
    inventory,
)
from src.services.operation.never_do import (
    is_never_do_coverage_hole,
    module_never_do_list,
)
from src.services.operation.recert import is_content_hash_void, raise_high_incident
from src.services.operation.rubric import (
    FAILURE_MODE_UNREADABLE,
    OPERATION_RUBRIC_VERSION,
    compute_rubric_dimension_spread,
    is_evidence_absent,
    is_spread_collapsed,
)
from src.services.operation.run_registry import (
    close_run,
    gate_result_for,
    open_run,
    sweep_timed_out_runs,
)
from src.services.operation.run_window import DEFAULT_RUN_WINDOW_MINUTES
from src.services.operation.scenarios import GATE_9_5_FLAG, validate_curriculum_submission
from src.services.operation.state_machine import OperationState, is_assignable
from src.utils.time import utcnow

router = APIRouter()


# =================================================================================================
# Submit curriculum
# =================================================================================================


@router.post("/curriculum", dependencies=[Depends(require_role("forge_owner"))])
async def submit_curriculum(
    body: ForgeOperationCurriculum, session: AsyncSession = Depends(get_session)
) -> dict:
    """Validate a curriculum submission against the Batch-3 rules + ADR-0049. Reject (422) on any
    violation. On success, upsert the bound instruction set and echo per-module cert levels, the
    declared absences and the Gate 9.5 flag.

    **A class a module cannot have may be declared not_applicable, with a reason, and accepted; a
    class that is neither supplied nor declared is still refused.** The declarations arrive on
    `module_not_applicable` (contract §10 A1.1) and the reason is already required by the schema,
    so a reasonless one 422s here before this function is reached — which is the same layering
    every other required field on this payload has.
    """
    scenarios = [s.model_dump() for s in body.operation_scenarios]
    requested_modules = sorted(
        {s.module_id for s in body.operation_scenarios}
        | {u.module_id for u in body.certification_units_requested if u.module_id}
    )
    result = validate_curriculum_submission(
        scenarios,
        module_never_do=body.module_never_do,
        module_not_applicable=body.module_not_applicable,
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
    never_do = list(body.module_never_do.get(ref.module_id, []))
    if existing is None:
        session.add(
            ForgeInstructionSet(
                forgeId=ref.forge_id,
                moduleId=ref.module_id,
                instructionVersion=ref.instruction_version,
                forgeApiVersion=ref.forge_api_version,
                authoredBy=ref.authored_by or "office",
                contentHash=ref.content_hash,
                neverDo=never_do,  # so an n/a can be told from a coverage hole (FIX 2)
            )
        )
        await session.commit()
    elif never_do and not existing.neverDo:
        # Backfill the never-do list if this submission declares one and the set didn't carry it.
        existing.neverDo = never_do
        await session.commit()

    return {
        "accepted": True,
        "module_levels": result.module_levels,
        # Every accepted declaration, module -> class -> WHY. Echoed because a level alone cannot
        # surface a cap: `certified_with_declared_absence` says a class was declared absent, and
        # only this says which one and on what grounds. ADR-0049 requires the cap be visible
        # somewhere and deliberately does not design where; this is the smallest honest version,
        # and it travels with the response the submitter already reads.
        "module_declared_absences": result.module_declared_absences,
        # The declared never-do entries, recorded and outstanding. A submitter may not author the
        # never_do_violation scenarios that would test them (ADR-0048), so what it gets back is an
        # acknowledgement that the obligation was received and is not yet exercised — rather than
        # the silence that omitting the list used to buy.
        "never_do_obligations": result.never_do_obligations,
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
    # Does the run's module declare a never-do list? A required-but-untested never-do dimension is a
    # coverage hole that blocks full certification (holds at provisional), not an n/a (FIX 2).
    module_has_never_do = bool(await module_never_do_list(session, ref.forge_id, ref.module_id))

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
        # Which SHAPE of coverage hole this is, when the battery told us. A dimension that went
        # unexercised while the protocol mode was reported is the candidate-side case: had the
        # probe been put and read, the dimension would carry a verdict. Absent the mode we do not
        # guess - `None` keeps the umbrella status and the gating decision it always produced.
        answer_unreadable = (
            FAILURE_MODE_UNREADABLE in (outcome.failure_modes_observed or [])
            if outcome.failure_modes_observed is not None
            else None
        )
        if void:
            state = OperationState.REVOKED.value
        elif not outcome.passed:
            state = OperationState.FAILED.value
        elif (
            is_evidence_absent(results_dicts)
            or is_spread_collapsed(spread, results_dicts)
            or is_never_do_coverage_hole(
                module_has_never_do, results_dicts, answer_unreadable=answer_unreadable
            )
        ):
            # Passed the bar, but nothing about the module was observed at all (ADR-0052), or the
            # rubric didn't discriminate (collapse), or a required never-do dimension went untested
            # (coverage hole) → full certification WITHHELD (ADR-0052 / FIX 1 / FIX 2).
            #
            # THREE INDEPENDENT WITHHOLDS, and the independence is the point. A
            # `protocol_conformance` FAIL explains why a never-do dimension went unexercised and
            # never discharges its hole: an explanation is not an exercise, and a unit that reached
            # `certified` because we understood why it was never tested would be the exact failure
            # FIX 2 exists to prevent.
            state = OperationState.PROVISIONAL.value
        else:
            state = OperationState.CERTIFIED.value

        # A cert that says something PASSED must name what answered. Everything else on
        # this row describes the exam — the instructions, the Forge version, the rubric —
        # and without the model it reads as *this agent passed* rather than *this agent,
        # on this model, passed*, so swapping the model leaves it looking current.
        #
        # Checked HERE rather than as a NOT NULL because the column is legitimately empty
        # for two shapes a constraint cannot distinguish: a timed-out run got no answer,
        # and a `department_context` unit is cleared by department state. The verdict
        # class is only known at this point.
        if state in (
            OperationState.CERTIFIED.value,
            OperationState.PROVISIONAL.value,
        ) and not (outcome.agent_model or "").strip():
            raise HTTPException(
                status_code=422,
                detail=(
                    f"agent_operation outcome for {outcome.agent_id}/{outcome.module_id} "
                    f"resolves to '{state}' and names no agent_model. A certification "
                    "that cannot say which model answered is one nobody can reproduce or "
                    "expire when the model moves. Send `provider/model`, e.g. "
                    "`ollama/llama3.1:8b`."
                ),
            )

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
            agentModel=outcome.agent_model,
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

    # Close the run this result answers, if one was opened for it. Nothing is created
    # here: a gate-result for a run SimForge never saw start is still recorded as certs,
    # it simply has no window to close. Opening one now would start a clock at the moment
    # the run ENDED, which is worse than no clock at all.
    if body.run_ref:
        await close_run(
            session,
            run_ref=body.run_ref,
            agent_states=[r.state for r in agent_results],
            department_states=[r.state for r in dept_results],
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
# Run window — a battery in flight, and the verdict a run that never finished resolves to
# =================================================================================================


@router.post("/run/start", dependencies=[Depends(require_role("compliance_analyst"))])
async def start_operation_run(
    body: OperationRunStartRequest, session: AsyncSession = Depends(get_session)
) -> OperationRunStarted:
    """Record that an operation battery has started.

    THE GAP THIS CLOSES. Until this call existed SimForge held no record of a run between
    the curriculum hand-over and the gate result, so a battery that hung produced nothing
    at all — no row, no verdict, no error — and the previous certification stayed in
    place. The Office maps TIMEOUT to `in_training` precisely so a hung run can never
    certify, and that mapping was unreachable because nothing observed the run.

    Idempotent: re-posting an open `run_ref` returns the existing row with its clock
    untouched. A retried hand-over must never extend the window of a run that is already
    hanging, which is the one case where restarting the clock hides the fault.
    """
    if body.unit not in ("A", "B"):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unknown_unit",
                # Not defaulted: The Office reads ONE verdict per run_ref and needs to
                # know which unit it is for. Guessing here would mis-file a certification.
                "detail": (
                    "unit must be 'A' (agent x forge x module) or 'B' "
                    f"(department x forge), got {body.unit!r}"
                ),
            },
        )

    existing = (
        await session.execute(select(OperationRun).where(OperationRun.runRef == body.run_ref))
    ).scalar_one_or_none()

    run = await open_run(
        session,
        run_ref=body.run_ref,
        unit=body.unit,
        forge_id=body.forge_id,
        instruction_content_hash=body.instruction_content_hash,
        rubric_kind=body.rubric_kind,
        rubric_version=body.rubric_version or OPERATION_RUBRIC_VERSION,
        module_id=body.module_id,
        agent_id=body.agent_id,
        department_id=body.department_id,
        scenario_count=body.scenario_count,
        coverage_denominator=body.coverage_denominator,
        window_minutes=body.window_minutes or DEFAULT_RUN_WINDOW_MINUTES,
    )
    await session.commit()

    return OperationRunStarted(
        run_ref=run.runRef,
        unit=run.unit,
        started_at=run.startedAt,
        window_minutes=run.windowMinutes,
        already_open=existing is not None,
    )


@router.get("/gate-result/{run_ref}", dependencies=[Depends(require_role("viewer"))])
async def read_gate_result(run_ref: str, session: AsyncSession = Depends(get_session)) -> dict:
    """The verdict of a run, in the shape The Office's response manifest declares.

    A run still open past its window reads TIMEOUT here even if the sweep has not stamped
    it yet — the answer a caller gets must not depend on how recently a background job
    ran. TIMEOUT resolves to `in_training` on their side and never to a pass.

    An unknown ref is a 404, not a `NOT_RUN` body: NOT_RUN requires a `unit` and a
    `rubric_version`, and SimForge has neither for a run it never received. Answering
    with invented ones would be a shape-valid response built out of guesses.
    """
    body = await gate_result_for(session, run_ref)
    if body is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "unknown_run_ref",
                "detail": (
                    f"SimForge has no record of run_ref {run_ref!r}. It was never opened via "
                    "POST /operation/run/start, so there is no window and no verdict to report."
                ),
            },
        )
    return body


@router.get("/battery-result/{run_ref}", dependencies=[Depends(require_role("viewer"))])
async def read_battery_result(run_ref: str, session: AsyncSession = Depends(get_session)) -> dict:
    """What a battery OBSERVED on this run - the second read, beside the gate verdict.

    **One `run_ref`, two reads, neither pretending to be the other.**
    `GET /gate-result/{run_ref}` answers whether the run reached a verdict, in the shape The
    Office's response manifest declares - a contract with a bound Pack module, which is why it is
    not extended to carry this. This answers what the battery saw: rubric results, per-class
    verdicts, failure modes, the model that answered.

    A run with a verdict and no battery behind it is a normal state, not an error: the gate-result
    path accepts a result The Office computed itself. Such a run reads `observed: false` here while
    reporting a real verdict there, and the two answers are both correct.

    **This route reads certifications; it cannot reach the battery.** ADR-0050 is unaffected -
    `battery_result` imports models only, and the walk from this module to
    `src.services.operation.battery` stays closed.
    """
    body = await battery_result_for(session, run_ref)
    if body is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "unknown_run_ref",
                "detail": (
                    f"SimForge has no record of run_ref {run_ref!r}. It was never opened via "
                    "POST /operation/run/start, so there is nothing a battery could have scored."
                ),
            },
        )
    return body


@router.post("/runs/sweep-timeouts", dependencies=[Depends(require_role("compliance_analyst"))])
async def sweep_run_timeouts(session: AsyncSession = Depends(get_session)) -> TimeoutSweepResult:
    """Stamp every open run past its own window as TIMEOUT.

    This is the half SimForge can do. The other half is The Office's deadline on
    unanswered submissions, and the two are not redundant: a worker that has died cannot
    report that it has died, so the case where SimForge is the thing that failed is
    exactly the case where this sweep is not running.

    A timed-out run is never recorded as `failed` and never carries a score. It was cut
    off, which proves nothing about the agent — calling it a failure both defames the
    agent and pollutes the metric that is supposed to show real failures.
    """
    # One `now` for the sweep and for the report, so `minutes_open` is measured against the
    # same instant the verdict was decided at rather than a few milliseconds later.
    now = utcnow()
    swept = await sweep_timed_out_runs(session, now=now)
    await session.commit()

    return TimeoutSweepResult(
        swept_at=now,
        timed_out=[
            TimedOutRun(
                run_ref=r.runRef,
                unit=r.unit,
                forge_id=r.forgeId,
                module_id=r.moduleId,
                agent_id=r.agentId,
                department_id=r.departmentId,
                verdict=r.verdict or "TIMEOUT",
                minutes_open=(now - r.startedAt).total_seconds() / 60.0,
                window_minutes=r.windowMinutes,
            )
            for r in swept
        ],
    )


# =================================================================================================
# Reads
# =================================================================================================


@router.get("/agents/{agent_id}", dependencies=[Depends(require_role("viewer"))])
async def agent_operation_view(agent_id: str, session: AsyncSession = Depends(get_session)) -> dict:
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


# =================================================================================================
# Held-out material — counts are inspectable, content is refused to everyone (ADR-0050)
# =================================================================================================
#
# Two routes, and the second one exists in order to say no.
#
# `GET /held-out/{forge}/{module}`            -> counts, and a digest of the authored set
# `GET /held-out/{forge}/{module}/scenarios`  -> 403, ALWAYS, at every role
#
# The refusal route is not an oversight and it is not a placeholder. ADR-0050's ruling is that no
# credential fetches the held-out set — not `forge_owner`, not the founder — because *an endpoint
# returning the corpus makes isolation a function of who holds a token*, and `Principal.has_role`
# already answers True to everything once `admin` is present. A 404 at this URL would read as "not
# built yet" and invite exactly the construction the ruling forbids; a 403 that names the ADR is the
# decision, left where the next author will look for it.


@router.get("/held-out/{forge_id}/{module_id}", dependencies=[Depends(require_role("viewer"))])
async def held_out_inventory(
    forge_id: str, module_id: str, session: AsyncSession = Depends(get_session)
) -> HeldOutInventoryResponse:
    """How much held-out material exists for this module. **Never what it says.**

    ADR-0050: *"eleven scenarios exist for this module" is inspectable; "here they are" is the
    exam.*
    An operator has a real question — was this module's refusal material ever authored, and against
    how many obligations — and a count answers it. Without this, the only way to know a held-out set
    exists is to read the code, which is the same defect as a `status` column nobody can check
    against the rows.

    The scenarios are authored inside `held_out.inventory` and never leave it. This handler cannot
    return a probe because it never holds one, which is a stronger property than a handler that
    holds one and remembers not to.
    """
    never_do = await module_never_do_list(session, forge_id, module_id)
    inv = inventory(module_id, never_do)
    return HeldOutInventoryResponse(
        forge_id=forge_id,
        module_id=inv.module_id,
        obligations_declared=inv.obligations_declared,
        scenarios_authored=inv.scenarios_authored,
        by_class=dict(inv.by_class),
        digest=inv.digest,
        gate_9_5_flag=GATE_9_5_FLAG,
    )


@router.get(
    "/held-out/{forge_id}/{module_id}/scenarios",
    dependencies=[Depends(require_role("viewer"))],
)
async def held_out_scenarios_are_never_returned(
    forge_id: str, module_id: str, principal: Principal = Depends(get_current_principal)
) -> dict:
    """**Always 403.** This is the refusal, and it is the one part of the isolation the engine can
    prove about itself.

    `GATE_9_5_FLAG` records that the engine cannot self-prove that whoever authors the held-out set
    is isolated from whoever could leak it — true, and unchanged. But *whether this service hands
    the corpus to a caller* is a question about this service, and it is answerable here by being
    refused rather than asserted in prose.

    **The refusal is unconditional, and it has to be.** `require_role("viewer")` on this route is
    not what refuses — it is there so the route is reachable enough to BE refused, because a 401 for
    an anonymous caller would prove nothing about a credentialled one. The refusal is below, it
    reads no role, and the principal is accepted only to be named in the response: a caller holding
    every role in the system gets the same answer as a caller holding one. That is what
    "no credential fetches the held-out set" means when it is code instead of a sentence.
    """
    raise HTTPException(
        status_code=403,
        detail={
            "error": HELD_OUT_CONTENT_REFUSED,
            "forge_id": forge_id,
            "module_id": module_id,
            "roles_held": sorted(principal.roles),
            "message": (
                "Held-out scenario content is never returned to any caller, at any role. An "
                "endpoint returning the corpus would make isolation a function of who holds a "
                "token, and a strong enough role gets everything — which is ADR-0048's refusal "
                "undone one endpoint over. The probe reaches the agent under test at run time, "
                "inside a battery; nobody fetches the set. Counts, and a digest, are at "
                f"GET /api/operation/held-out/{forge_id}/{module_id}. See ADR-0050."
            ),
            "inspectable_instead": f"/api/operation/held-out/{forge_id}/{module_id}",
            "adr": "ADR-0050",
        },
    )


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


def _serialize_cert(c: OperationCertification) -> dict:
    """One operation cert as the UI consumes it — denominator + named-list results + version stamp,
    never merged with a domain result."""
    return {
        "id": c.id,
        "unit_type": c.unitType,
        "state": c.state,
        "assignable": is_assignable(c.state),
        "forge_id": c.forgeId,
        "module_id": c.moduleId,
        "agent_id": c.agentId,
        "department_id": c.departmentId,
        "forge_context": c.forgeContext,
        "venture_context": c.ventureContext,
        "instruction_version": c.instructionVersion or None,
        "forge_api_version": c.forgeApiVersion or None,
        "operation_rubric_version": c.operationRubricVersion,
        "functions_certified": c.functionsCertified,
        "functions_in_module": c.functionsInModule,  # DENOMINATOR
        "max_certified_trust_tier": c.maxCertifiedTrustTier,
        "operation_rubric_results": c.operationRubricResults or [],  # NAMED LIST
        "rubric_dimension_spread": c.rubricDimensionSpread,
        "escalation_path_verified": c.escalationPathVerified,
        "compliance_coupling_verified": c.complianceCouplingVerified,
        "expires_at": c.expiresAt.isoformat() if c.expiresAt else None,
    }


@router.get("/certs", dependencies=[Depends(require_role("viewer"))])
async def list_operation_certs(
    unit_type: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """All operation certs (both unit types), each carrying its own denominator + named-list results
    + operation_rubric_version. Shown beside the domain cert, never as one merged score."""
    stmt = select(OperationCertification).order_by(OperationCertification.createdAt.desc())
    if unit_type is not None:
        stmt = stmt.where(OperationCertification.unitType == unit_type)
    certs = (await session.execute(stmt)).scalars().all()
    return {
        "operation_rubric_version": OPERATION_RUBRIC_VERSION,
        "certs": [_serialize_cert(c) for c in certs],
        "total": len(certs),
    }


@router.get("/side-by-side", dependencies=[Depends(require_role("viewer"))])
async def side_by_side_view(session: AsyncSession = Depends(get_session)) -> dict:
    """The Batch-6 surface: each agent operation cert paired with that agent's DOMAIN cert — two
    records, two denominators, two version stamps, never merged into one number."""
    from src.services.operation import views

    return await views.side_by_side(session)


@router.get("/coverage", dependencies=[Depends(require_role("viewer"))])
async def coverage_overview(session: AsyncSession = Depends(get_session)) -> dict:
    """Coverage across all forges with honest denominators; thin modules flagged (Batch 6)."""
    from src.services.operation import views

    return await views.coverage(session)


@router.get("/dept-context", dependencies=[Depends(require_role("viewer"))])
async def dept_context_view(session: AsyncSession = Depends(get_session)) -> dict:
    """Unit-B department-context certs (department × forge × context × venture)."""
    from src.services.operation import views

    return await views.dept_context(session)


@router.get("/capacity-view", dependencies=[Depends(require_role("viewer"))])
async def capacity_view(session: AsyncSession = Depends(get_session)) -> dict:
    """The §8 capacity numbers shaped for the UI: per-module Office-owned free/allocated (labeled)
    vs SimForge-owned produced-but-not-certified, plus totals."""
    from src.services.operation import views

    return await views.capacity(session)


@router.get("/capacity", dependencies=[Depends(require_role("viewer"))])
async def capacity(session: AsyncSession = Depends(get_session)) -> dict:
    """The §8 capacity numbers SimForge owns — produced-but-not-certified (never_certified /
    in_training) and the certified count — plus the Office-owned allocation split, which SimForge
    does NOT track and reports as null so it's never mistaken for a SimForge number."""
    agent_certs = (
        (
            await session.execute(
                select(OperationCertification).where(
                    OperationCertification.unitType == "agent_operation"
                )
            )
        )
        .scalars()
        .all()
    )
    by_state: dict[str, int] = {}
    for c in agent_certs:
        by_state[c.state] = by_state.get(c.state, 0) + 1
    certified = by_state.get(OperationState.CERTIFIED.value, 0)
    produced_not_certified = by_state.get(OperationState.NEVER_CERTIFIED.value, 0) + by_state.get(
        OperationState.IN_TRAINING.value, 0
    )
    return {
        "simforge_owned": {
            "certified": certified,
            "produced_but_not_certified": produced_not_certified,
            "by_state": by_state,
        },
        "office_owned": {
            "certified_and_free": None,  # allocator state lives with The Office
            "certified_but_allocated": None,
            "note": "allocation split is Office-owned; SimForge does not track it",
        },
    }

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
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import Principal, get_current_principal, require_role
from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.operation_cert import OperationCertification
from src.models.operation_run import OperationRun
from src.models.operation_scenario import OperationScenarioSubmission
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
from src.services.agent_runtime.model_identity import ModelIdentity, identity_is_complete
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
    instruction_set_hashes,
    is_never_do_coverage_hole,
    module_never_do_list,
)
from src.services.operation.recert import is_content_hash_void, raise_high_incident
from src.services.operation.rubric import (
    CHANNEL_RESTRAINT,
    CHANNEL_UNSTATED,
    FAILURE_MODE_UNREADABLE,
    OPERATION_RUBRIC_VERSION,
    SCORE_MEASURE_UNSTATED,
    VERDICT_FAIL,
    WITHHOLD_COMPETENCE_UNEXERCISED,
    WITHHOLD_EVIDENCE_ABSENT,
    WITHHOLD_NEVER_DO_UNTESTED,
    WITHHOLD_NO_MODEL_FILE,
    WITHHOLD_RUBRIC_UNDISCRIMINATING,
    channels_failed,
    collapse_measure,
    count_classes_exercised,
    is_evidence_absent,
    is_rubric_undiscriminating,
    tier_for_channels,
)
from src.services.operation.run_registry import (
    UnitOutcome,
    close_run,
    gate_result_for,
    open_run,
    sweep_timed_out_runs,
)
from src.services.operation.run_window import DEFAULT_RUN_WINDOW_MINUTES
from src.services.operation.scenarios import (
    GATE_9_5_FLAG,
    is_competence_unexercised,
    validate_curriculum_submission,
)
from src.services.operation.state_machine import OperationState, is_assignable
from src.services.operation.trust_tier import tier_for_state
from src.telemetry.logging import get_logger
from src.utils.time import utcnow

log = get_logger("operation")
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

    # ADR-0069 P1: THE ANSWER KEY IS KEPT.
    #
    # Until this, `body.operation_scenarios` was validated and discarded - so nothing could re-read
    # what a venture said its agent should do, nothing could RUN the seven submittable classes, and
    # therefore only the two held-out dimensions ever carried a score. Both at 1.0 on a clean run
    # is a collapsed spread, which is why no run could reach `certified`.
    #
    # DELETE-THEN-INSERT, not an upsert per scenario. A curriculum is a SET submitted whole: a
    # re-post of the same one must not double it, and a re-post of a CHANGED one must not leave
    # last time's scenarios standing beside this time's. The key is the same natural key the
    # instruction set upserts on, so the two halves of one submission agree about what "the same
    # submission" means without either asserting it.
    await session.execute(
        delete(OperationScenarioSubmission).where(
            OperationScenarioSubmission.forgeId == ref.forge_id,
            OperationScenarioSubmission.moduleId == ref.module_id,
            OperationScenarioSubmission.instructionContentHash == ref.content_hash,
        )
    )
    for ordinal, scenario in enumerate(body.operation_scenarios):
        session.add(
            OperationScenarioSubmission(
                forgeId=ref.forge_id,
                # The SCENARIO's module, not the ref's: a curriculum may carry scenarios for
                # several modules and `requested_modules` above is built from exactly that.
                moduleId=scenario.module_id,
                instructionContentHash=ref.content_hash,
                scenarioClass=scenario.scenario_class,
                instructionSection=scenario.instruction_section,
                situation=scenario.situation,
                expectedBehavior=scenario.expected_behavior,
                expectedEscalation=scenario.expected_escalation,
                neverDoEntry=scenario.never_do_entry,
                # ADR-0083 - the transcribable half, stored beside the prose. `None` throughout
                # when the submitter sent no `expected_answer`, which is a scenario that can be
                # read and cannot be graded by transcription.
                expectedAct=(scenario.expected_answer.act if scenario.expected_answer else None),
                expectedRecord=(
                    scenario.expected_answer.record if scenario.expected_answer else None
                ),
                recordSubject=(
                    scenario.expected_answer.record_subject if scenario.expected_answer else None
                ),
                recordClaim=(
                    scenario.expected_answer.record_claim if scenario.expected_answer else None
                ),
                recordClaimOptions=(
                    scenario.expected_answer.record_claim_options
                    if scenario.expected_answer
                    else None
                ),
                expectedCaveat=(
                    scenario.expected_answer.expected_caveat if scenario.expected_answer else None
                ),
                ordinal=ordinal,
            )
        )

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
    else:
        # The instruction set was already correct, and the SCENARIOS still need committing: the
        # delete-then-insert above is in this transaction, and a re-submission that changed only
        # its scenarios would otherwise be rolled back at the end of the request.
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
    # ADR-0096: the channel travels with the verdict. Dropping it here would have every row read
    # as `unstated_by_the_submitter` one line after the submitter stated it.
    d: dict = {"dimension": item.dimension, "channel": item.channel, "verdict": item.verdict}
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
    # ADR-0091 - the RUN's hash, not the Office-declared one. They are the same value except when
    # they are not, and the case where they differ is exactly `void` above: a run executed against
    # a set the submitter did not declare. Asking `ref.content_hash` there would describe the
    # coverage of a set this run never saw.
    module_has_never_do = bool(
        await module_never_do_list(
            session, ref.forge_id, ref.module_id, body.run_content_hash
        )
    )

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
    #: What the RUN is closed with, kept beside the outbound results because the two carry
    #: different things: the Office-facing result shape is a contract and says nothing about the
    #: model or the bar, while the run has to record both.
    agent_units: list[UnitOutcome] = []
    for outcome in body.agent_outcomes:
        results_dicts = [_out_dim(r) for r in outcome.operation_rubric_results]
        # ADR-0070: the number AND the rule that produced it, written by one call. How many
        # scenario classes carried a real verdict is the second half of the v2 question - not
        # "did the scores agree" but "were the dimensions independently sourced at all".
        spread, spread_measure = collapse_measure(results_dicts)
        classes_exercised = count_classes_exercised(outcome.per_scenario_class_results)
        # Which SHAPE of coverage hole this is, when the battery told us. A dimension that went
        # unexercised while the protocol mode was reported is the candidate-side case: had the
        # probe been put and read, the dimension would carry a verdict. Absent the mode we do not
        # guess - `None` keeps the umbrella status and the gating decision it always produced.
        answer_unreadable = (
            FAILURE_MODE_UNREADABLE in (outcome.failure_modes_observed or [])
            if outcome.failure_modes_observed is not None
            else None
        )
        # FOUR INDEPENDENT WITHHOLDS, each with a name, assembled as a LIST rather than collapsed
        # into one boolean - the independence is the point and so is the record. A
        # `protocol_conformance` FAIL explains why a never-do dimension went unexercised and never
        # discharges its hole: an explanation is not an exercise, and a unit that reached
        # `certified` because we understood why it was never tested would be the exact failure
        # FIX 2 exists to prevent.
        withheld: list[str] = []
        if is_evidence_absent(results_dicts):
            withheld.append(WITHHOLD_EVIDENCE_ABSENT)
        if is_rubric_undiscriminating(
            spread,
            results_dicts,
            measure=spread_measure,
            classes_exercised=classes_exercised,
        ):
            withheld.append(WITHHOLD_RUBRIC_UNDISCRIMINATING)
        if is_never_do_coverage_hole(
            module_has_never_do, results_dicts, answer_unreadable=answer_unreadable
        ):
            withheld.append(WITHHOLD_NEVER_DO_UNTESTED)
        # ADR-0072 - the breadth rule. Only the held-out half ran, so the result is a claim about
        # DISCIPLINE with nothing said about COMPETENCE. Until ADR-0070 the collapse check withheld
        # this case by accident (two dimensions, both pinned to 1.0, variance 0.0); it is named
        # here so it is chosen rather than inherited.
        if is_competence_unexercised(outcome.per_scenario_class_results):
            withheld.append(WITHHOLD_COMPETENCE_UNEXERCISED)

        # ADR-0092 RULING 1, ON THE RECEIVING SIDE.
        #
        # `outcome.passed` arrives over the wire. SimForge's own builder now derives it from the
        # merged result, but this handler accepts a `GateResultRequest` from anyone, and the rule
        # is about the CERTIFICATION rather than about who computed the boolean: an agent that
        # fails a competence dimension is not certified, whatever was sent.
        #
        # Not a 422. A submitter reporting a dimension FAIL is telling the truth about the exam;
        # refusing the payload would lose the result. The verdict is corrected instead, and the
        # row records both halves - `state` failed, `operationRubricResults` saying why.
        dimensions_failed = [
            r["dimension"]
            for r in results_dicts
            if r.get("verdict") == VERDICT_FAIL and r.get("channel") == CHANNEL_RESTRAINT
        ]
        if dimensions_failed and outcome.passed:
            log.warning(
                "gate_result_pass_contradicted_by_its_own_dimensions",
                run_ref=run_ref,
                agent=outcome.agent_id,
                module=outcome.module_id,
                failed_dimensions=dimensions_failed,
            )

        # ADR-0096 - A TIER READS THE CHANNEL IT NEEDS.
        #
        # `propose` requires RESTRAINT alone: a person reads every output, and in every sampled
        # case the caveat was correct even where the label was wrong. `auto_execute` requires both,
        # because a mislabelled escalation never reaches a human.
        #
        # So a disposition failure no longer fails the run. It CAPS it. ADR-0092 ruling 1 said an
        # agent that fails a competence dimension is not certified, and this refines it rather
        # than reversing it: the question "failed at what?" now has an answer, and the tier is
        # where it is answered.
        channel_tier = tier_for_channels(results_dicts, outcome.max_certified_trust_tier)
        restraint_failed = CHANNEL_RESTRAINT in channels_failed(results_dicts)
        unstated_failed = CHANNEL_UNSTATED in channels_failed(results_dicts)
        if unstated_failed:
            log.warning(
                "gate_result_verdict_names_no_channel",
                run_ref=run_ref,
                agent=outcome.agent_id,
                module=outcome.module_id,
            )

        if void:
            state = OperationState.REVOKED.value
        elif not outcome.passed or restraint_failed or unstated_failed:
            state = OperationState.FAILED.value
        elif withheld:
            state = OperationState.PROVISIONAL.value
        else:
            state = OperationState.CERTIFIED.value

        # THE FOURTH WITHHOLD (ADR-0060): the exam was not sat on a model file.
        #
        # Ivan's ruling is that a certification counts only if it was earned on the exact model the
        # agent runs in production, and Village agents run on local models. A cloud provider stays
        # available for practice runs - so a cloud-examined result is a real result that is not a
        # certification, which is what `provisional` has meant here since the Rev-2 audit: not
        # certified, not a failure.
        #
        # **This is a PROXY for the ruling and says so.** The real test is "the same model as
        # production", and SimForge cannot read the Village's model configuration - it lives in
        # another repository behind no seam. What is checkable here is narrower: whether anything
        # with a model file on this machine answered at all. The rest of the rule is recorded,
        # computable from `fingerprint`, and not enforced; see ADR-0060 and the report.
        identity = ModelIdentity.from_record(outcome.model_identity)
        if state == OperationState.CERTIFIED.value and identity and not identity.has_model_file:
            state = OperationState.PROVISIONAL.value
            withheld.append(WITHHOLD_NO_MODEL_FILE)

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

        # ...and it must say WHICH model, in the detail that lets the exam be re-sat and drift
        # be seen. `agent_model` above is a label: the same tag re-pulled at a different
        # quantization, or served at a different temperature, produces the same string and a
        # different candidate. ADR-0060 is the ruling; this is where "a result with no model
        # identity is never reported as a pass" is true rather than hoped for.
        #
        # Reached only for `certified`. A `provisional` hold has no certification to qualify, and
        # the withhold above has already caught the one case - no model file - that a complete
        # record could still be wrong about.
        # ADR-0093 - A SCORE SAYS WHAT IT MEASURES, AND AN UNLABELLED ONE SAYS SO BY NAME.
        #
        # Not a 422. ADR-0087 settled this shape when `situation` was declared: SimForge declares
        # a field first, and refusing every payload that has not yet learned to fill it would stop
        # a venture that is already certifying. Not a guess either - labelling an unlabelled number
        # `held_out_pass_rate_v1` would invent a fact about somebody else's measure, which is the
        # defect being repaired pointing the other way.
        #
        # `unstated_by_the_submitter` says exactly what is known, satisfies the CHECK, and is one
        # grep away for whoever asks how many rows still carry a number nobody described.
        score_measure = (outcome.score_measure or "").strip() or None
        if outcome.score is not None and score_measure is None:
            score_measure = SCORE_MEASURE_UNSTATED
            log.warning(
                "gate_result_score_names_no_measure",
                run_ref=run_ref,
                agent=outcome.agent_id,
                module=outcome.module_id,
                score=outcome.score,
            )

        if state == OperationState.CERTIFIED.value:
            missing_identity = identity_is_complete(outcome.model_identity)
            if missing_identity:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"agent_operation outcome for {outcome.agent_id}/{outcome.module_id} "
                        f"resolves to 'certified' and its model identity is missing "
                        f"{', '.join(missing_identity)}. A certification counts only if it was "
                        "earned on the exact model the agent runs in production - the model name, "
                        "the model file with its size and quantization, and the generation "
                        "settings. A name alone cannot say which of those changed."
                    ),
                )

        # The tier is CAPPED here rather than trusted from the outcome. A battery declares the
        # ceiling its exam can justify before the state is known; whether the unit reached it is
        # decided above, from the rubric, the spread and the coverage holes. Trusting the declared
        # value would write `propose` onto a `failed` row - which `views.py` already has to hide
        # at render time, a symptom of the cap living nowhere.
        # ADR-0096. Two caps, in order: the channels decide the strongest tier the exam justifies,
        # and the state decides whether any tier is carried at all. `tier_for_state` still refuses
        # a tier on anything but `certified`, so a failed row carries none whatever the channels
        # said.
        tier = tier_for_state(state, channel_tier)

        # A pass must carry the basis it was earned on, for the same reason it must name the model.
        #
        # THIS IS THE REFUSAL THAT MAKES "an ungraded run never reports a pass" TRUE. The Office's
        # `record_result` will not write a `certified` row without a tier, so before this check a
        # PASS with no basis was not rejected anywhere - it was produced, reported, polled, and
        # refused at the far side of the boundary, where the reason reads as an Office problem.
        # Refusing it here means the run never reaches PASS at all, and the message names which
        # fact is missing.
        #
        # `certified` only. A `provisional` hold has no certified tier BY DEFINITION - the
        # certification was withheld - and demanding one would invite the placeholder The Office's
        # own comment refuses.
        if state == OperationState.CERTIFIED.value:
            missing = [
                name
                for name, value in (
                    ("score", outcome.score),
                    ("threshold", outcome.threshold),
                    ("certified_tier", tier),
                )
                if value is None
            ]
            if missing:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"agent_operation outcome for {outcome.agent_id}/{outcome.module_id} "
                        f"resolves to 'certified' and carries no {', '.join(missing)}. A pass "
                        "nobody can place is not a pass: The Office caps a declared tier with "
                        "the certified one and refuses a certification without it, and a score "
                        "with no threshold beside it is a number with no bar. Send what the "
                        "battery measured, or report the outcome it actually reached."
                    ),
                )

        cert = OperationCertification(
            unitType="agent_operation",
            state=state,
            forgeId=outcome.forge_id,
            instructionVersion=ref.instruction_version,
            forgeApiVersion=ref.forge_api_version,
            instructionContentHash=body.run_content_hash,
            # ADR-0092 RULING 4. WHICH ANSWER KEYS THIS WAS GRADED AGAINST.
            #
            # Until now the binding was INFERRED: `submitted_keys_for` selects by
            # (forge, module, instruction hash), so the key set was implied by a hash of the
            # INSTRUCTIONS and written down nowhere. Two things could change underneath it - a key
            # edited, a key added - without the instruction hash moving a byte, and no row could
            # say whether the exam it recorded had seen them.
            #
            # NULL where no submitted keys were put, which is the honest value: a held-out-only
            # exam was graded against no answer key, and a digest of the empty set would say it
            # was graded against one.
            scenarioSetHash=outcome.scenario_set_hash,
            # ADR-0093. The number and the rule that produced it, on the row that is read on its
            # own. A score with no measure is refused by a CHECK rather than stored unreadable.
            score=outcome.score,
            scoreMeasure=score_measure,
            operationRubricVersion=op_rubric_version,
            agentId=outcome.agent_id,
            moduleId=outcome.module_id,
            functionsCertified=outcome.functions_certified,
            functionsInModule=outcome.functions_in_module,
            maxCertifiedTrustTier=tier,
            agentModel=outcome.agent_model,
            # Recorded on EVERY result, certified or not. A failed run's candidate is the fact
            # that makes the failure reproducible, and a provisional hold's is what says why it
            # was held.
            agentModelIdentity=identity.as_record() if identity else None,
            examAttempts=list(outcome.attempts) or None,
            perScenarioClass={
                r.scenario_class: r.verdict for r in outcome.per_scenario_class_results
            },
            operationRubricResults=results_dicts,
            rubricDimensionSpread=spread,
            rubricSpreadMeasure=spread_measure,
            # WHY it was held, recorded rather than left for each reader to re-derive - and ONLY
            # when a withhold actually produced the state. A run that FAILED the bar was not
            # withheld, and listing what else was wrong with it would describe a hold that never
            # happened.
            withheldBecause=(
                withheld if state == OperationState.PROVISIONAL.value and withheld else None
            ),
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
                max_certified_trust_tier=tier,
                model_identity=identity.as_record() if identity else None,
                operation_rubric_results=outcome.operation_rubric_results,
                rubric_dimension_spread=spread,
                per_scenario_class_results=outcome.per_scenario_class_results,
                functions_certified=outcome.functions_certified,
                functions_in_module=outcome.functions_in_module,
                failure_modes_observed=list(outcome.failure_modes_observed),
                expires_at=outcome.expires_at,
            )
        )
        agent_units.append(
            UnitOutcome(
                state=state,
                score=outcome.score,
                threshold=outcome.threshold,
                certified_tier=tier,
                agent_model=outcome.agent_model,
                model_identity=identity.as_record() if identity else None,
            )
        )

    dept_results: list[DepartmentContextCertResult] = []
    dept_units: list[UnitOutcome] = []
    for d_outcome in body.department_outcomes:
        # UNIT B, OPTION A (ADR-0062). Until this, `passed` alone decided, and
        # `escalation_path_verified` / `compliance_coupling_verified` both default to FALSE - so a
        # department certified on a payload that verified nothing, which is to say it passed
        # because nobody ticked "no".
        #
        # Both must now be true for `certified`; either missing holds the unit at `provisional`.
        #
        # **This is a stop-gap and Ivan named it one.** The two fields are still ASSERTIONS by the
        # submitter, not measurements - nothing here put a scenario to a department and watched
        # where the hand-over went. Option B, a real escalation-path test, is the answer and is not
        # built. What this buys is that a department can no longer pass in silence, and the
        # difference between "verified" and "nobody said otherwise" is now visible in the state.
        verified = (
            d_outcome.escalation_path_verified and d_outcome.compliance_coupling_verified
        )
        if void:
            d_state = OperationState.REVOKED.value
        elif not d_outcome.passed:
            d_state = OperationState.FAILED.value
        elif verified:
            d_state = OperationState.CERTIFIED.value
        else:
            # Not a failure: nothing was shown to be wrong. Not a certification either: nothing
            # was shown to be right. That is what `provisional` has meant since the Rev-2 audit.
            d_state = OperationState.PROVISIONAL.value
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
        # A department context carries no score, no tier and no model, and that is not an omission
        # to fix later: Unit B is cleared by whether the escalation path and the compliance
        # coupling were verified, and nothing sat an exam. See the Unit-B note in `battery.py`.
        dept_units.append(UnitOutcome(state=d_state))

    # Close the run this result answers, if one was opened for it. Nothing is created
    # here: a gate-result for a run SimForge never saw start is still recorded as certs,
    # it simply has no window to close. Opening one now would start a clock at the moment
    # the run ENDED, which is worse than no clock at all.
    if body.run_ref:
        await close_run(
            session,
            run_ref=body.run_ref,
            agent_outcomes=agent_units,
            department_outcomes=dept_units,
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
        village_agent_ref=body.village_agent_ref,
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
                # ADR-0070 - the number is unreadable without the rule that produced it.
                "rubric_spread_measure": c.rubricSpreadMeasure,
                "withheld_because": c.withheldBecause or [],  # ADR-0072
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
    forge_id: str,
    module_id: str,
    content_hash: str | None = None,
    session: AsyncSession = Depends(get_session),
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
    # ADR-0091. The held-out set is authored FROM the never-do list, so "how much material exists
    # for this module" has as many answers as the module has instruction sets. It had two on
    # `capital-forge/statement_ingest` and this route answered for whichever row came back first.
    #
    # `content_hash` is optional because one set is the ordinary case and requiring it would make
    # every existing caller pass a value it can already infer. When there is more than one, the
    # route REFUSES and names them: an operator who did not know a module had two sets is better
    # served by being told than by a number that is true of one of them.
    hashes = await instruction_set_hashes(session, forge_id, module_id)
    if content_hash is None:
        if len(hashes) > 1:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "more_than_one_instruction_set_for_this_module",
                    "forge_id": forge_id,
                    "module_id": module_id,
                    "content_hashes": hashes,
                    "hint": "pass ?content_hash= to say which set this question is about",
                },
            )
        content_hash = hashes[0] if hashes else ""
    never_do = await module_never_do_list(session, forge_id, module_id, content_hash)
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
        # ADR-0070 - the number is unreadable without the rule that produced it.
        "rubric_spread_measure": c.rubricSpreadMeasure,
        "withheld_because": c.withheldBecause or [],  # ADR-0072
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

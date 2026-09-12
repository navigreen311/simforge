"""The second read: what a battery observed, keyed by the same `run_ref`.

ONE run_ref, TWO READS
======================

`gate_result_for` answers **the gate question** — did this run reach a verdict, and what was it.
That body is enumerated in The Office's `simforge_response_manifest.json`, and a key that is not in
the manifest fails their `validate_response` on arrival. It is a contract, not a return value, and
`gate_result` is a **bound module in the Pack** — changing what it returns changes what a bound
module does. So it is not touched here.

This answers **the battery question** — what did the battery actually observe on that run. Rubric
results, per-class verdicts, failure modes, the model that answered. Neither read pretends to be the
other, and neither is derivable from the other: a run can have a verdict with no battery behind it
(The Office posted the result itself), and a battery can have observed something on a run whose
verdict later changed.

THE JOIN, AND THAT IT IS A LOOKUP RATHER THAN A KEY
===================================================

**`OperationCertification` carries no `runRef` column.** The link from a run to what a battery
observed is the natural tuple `(forgeId, moduleId, agentId)` read off the run, plus the run's own
window as a time bound. That is a lookup, not an identity: it is not declared, not unique, and not
enforced anywhere.

Two consequences are stated rather than discovered later:

* **A re-run of the same agent on the same module produces rows this cannot tell apart** except by
  time. `since` exists for that reason and defaults to the run's own `startedAt`.
* **A certification written for this tuple by something that was not this run** matches too. The
  gate-result path accepts a result for a run SimForge never saw, by design, and such a row is
  indistinguishable here from one this run produced.

Both are properties of the schema as it stands, not of this function. Closing them means putting
the `run_ref` on the certification row, which is a migration and a contract question, and is not
done here.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_cert import OperationCertification
from src.models.operation_run import OperationRun

#: Returned when the run exists and nothing has been observed for it. Distinct from a 404: the run
#: is real and no battery has reported, which is exactly the state the whole system sat in.
NO_BATTERY_RESULT = "no_battery_result_for_this_run"


async def battery_result_for(session: AsyncSession, run_ref: str) -> dict | None:
    """What a battery observed for `run_ref`. `None` when SimForge has no record of the ref.

    Deliberately shaped like `gate_result_for` in its failure mode - `None` for an unknown ref
    rather than an invented empty body - so a caller handles the two reads the same way.
    """
    run = (
        await session.execute(select(OperationRun).where(OperationRun.runRef == run_ref))
    ).scalar_one_or_none()
    if run is None:
        return None

    body: dict = {
        "run_ref": run.runRef,
        "unit": run.unit,
        "forge_id": run.forgeId,
        "module_id": run.moduleId,
        "agent_id": run.agentId,
        "observed": False,
        "reason": NO_BATTERY_RESULT,
        "certifications": [],
    }
    if not run.moduleId or not run.agentId:
        # A Unit-B or department run has no agent/module tuple to look up. Not an error -
        # the battery has nothing to say about it, and neither does this read.
        return body

    rows = (
        (
            await session.execute(
                select(OperationCertification)
                .where(
                    OperationCertification.forgeId == run.forgeId,
                    OperationCertification.moduleId == run.moduleId,
                    OperationCertification.agentId == run.agentId,
                    OperationCertification.unitType == "agent_operation",
                    OperationCertification.createdAt >= run.startedAt,
                )
                .order_by(OperationCertification.createdAt)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return body

    body["observed"] = True
    body.pop("reason")
    body["certifications"] = [
        {
            "state": c.state,
            "operation_rubric_version": c.operationRubricVersion,
            "instruction_content_hash": c.instructionContentHash,
            "agent_model": getattr(c, "agentModel", None),
            "per_scenario_class": c.perScenarioClass,
            "operation_rubric_results": c.operationRubricResults,
            "rubric_dimension_spread": c.rubricDimensionSpread,
            "failure_modes_observed": c.failureModesObserved,
            "created_at": c.createdAt.isoformat() if c.createdAt else None,
        }
        for c in rows
    ]
    #: Stated on the body rather than left for the reader to infer, because the join is a lookup.
    body["join"] = "natural_key(forge_id, module_id, agent_id) bounded by run.startedAt"
    return body

"""The Office posts a Unit B outcome through the bridge, and the gate-result writer records it.

ADR-0161. The first write The Office makes through `/office`. Until it, The Office posted its
attestations to `/office/gate_result`, which is a read: the outcome was ignored, the reply was the
run's status, The Office's manifest refused that reply, and every department run since September
timed out with an attestation sitting on The Office's side.

WHAT THIS DOES NOT DO
=====================

    It decides no verdict. The state comes from `routers.operation.gate_result`, the writer every
    gate result already goes through: both flags verified is `certified`, a flag missing is
    `provisional`, `passed: false` is `failed` (ADR-0062 option A). Ivan's ruling of 23 October
    2026 says `passed: false` means the attester recorded a defect; The Office owns sending it so.

    It is not a hand-over test. Nothing here puts a scenario to a department, and
    `DEPARTMENT_HANDOVER_TEST` stays False.

WHO MAY POST
============

    The Office, with its tenant credential, for a Unit B run it minted, under the venture that run
    names, carrying department outcomes only. Every call with the credential is audited, refusals
    included. A run that does not exist, or belongs to another venture, gets one 404 whatever the
    cause, so the call cannot probe which runs exist.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.department_outcome import DepartmentOutcomePost
from src.models.operation_run import OperationRun
from src.schemas.operation_payloads import (
    DepartmentOutcomeReply,
    DepartmentOutcomeRequest,
    GateResultRequest,
    InstructionSetRef,
)
from src.services.operation.partition_roster import venture_of_run_ref

#: Refusal codes, recorded on the audit row. The four lookup refusals share one 404 on the wire.
REFUSED_NO_IDEMPOTENCY_KEY = "no_idempotency_key"
REFUSED_PAYLOAD_INVALID = "payload_invalid"
REFUSED_KEY_REUSED = "idempotency_key_reused_with_another_payload"
REFUSED_NOT_OFFICE_MINTED = "run_ref_not_minted_by_the_office"
REFUSED_NO_VENTURE = "no_office_venture_header"
REFUSED_ANOTHER_VENTURE = "run_belongs_to_another_venture"
REFUSED_UNKNOWN_RUN = "no_such_run"
REFUSED_NOT_UNIT_B = "not_a_department_run"
REFUSED_OUTCOME_MISMATCH = "outcome_names_another_department_or_forge"
REFUSED_ALREADY_CLOSED = "run_already_has_a_verdict"

#: The lookup refusals: one status, one message.
NOT_FOUND_REFUSALS = frozenset(
    {REFUSED_NOT_OFFICE_MINTED, REFUSED_NO_VENTURE, REFUSED_ANOTHER_VENTURE, REFUSED_UNKNOWN_RUN}
)

#: The status each refusal is answered with.
REFUSAL_STATUS: dict[str, int] = {
    REFUSED_NO_IDEMPOTENCY_KEY: 422,
    REFUSED_PAYLOAD_INVALID: 422,
    REFUSED_NOT_UNIT_B: 422,
    REFUSED_OUTCOME_MISMATCH: 422,
    REFUSED_KEY_REUSED: 409,
    REFUSED_ALREADY_CLOSED: 409,
    **{code: 404 for code in NOT_FOUND_REFUSALS},
}

#: A run closed by the sweep for want of an answer. A result arriving after it is still recorded
#: (`close_run`): an outcome that arrived is better evidence than a deadline that passed.
_TIMEOUT = "TIMEOUT"


@dataclass(frozen=True, slots=True)
class PostResult:
    """One call's outcome. `reply` is None when it was refused."""

    reply: dict[str, Any] | None
    refusal: str | None = None
    #: Pydantic's violations, for a payload refusal only.
    violations: list[dict[str, Any]] | None = None

    @property
    def status_code(self) -> int:
        return 200 if self.refusal is None else REFUSAL_STATUS[self.refusal]


def payload_digest(payload: dict[str, Any]) -> str:
    """sha256 of the payload as canonical JSON: what makes a retry the same call."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _reply(run_ref: str, recorded: int, status: str) -> dict[str, Any]:
    # Validated on the way out: a fifth key is a 500 here rather than a refusal at The Office.
    return DepartmentOutcomeReply(
        run_ref=run_ref, accepted=True, recorded=recorded, status=status
    ).model_dump()


async def _prior(session: AsyncSession, key: str) -> DepartmentOutcomePost | None:
    return (
        await session.execute(
            select(DepartmentOutcomePost).where(
                DepartmentOutcomePost.idempotencyKey == key,
                DepartmentOutcomePost.outcome == "recorded",
            )
        )
    ).scalar_one_or_none()


async def _lookup_refusal(
    session: AsyncSession, run_ref: str, office_venture: str | None
) -> tuple[str | None, OperationRun | None]:
    """The run this post closes, or why it may not. The ADR-0153 order: mint, header, venture,
    existence - and only then anything about the run itself."""
    venture = venture_of_run_ref(run_ref)
    if venture is None:
        return REFUSED_NOT_OFFICE_MINTED, None
    if not office_venture or not office_venture.strip():
        return REFUSED_NO_VENTURE, None
    if venture != office_venture.strip():
        return REFUSED_ANOTHER_VENTURE, None
    run = (
        await session.execute(
            select(OperationRun)
            .where(OperationRun.runRef == run_ref)
            .order_by(OperationRun.sitting.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if run is None:
        return REFUSED_UNKNOWN_RUN, None
    return None, run


def _run_refusal(run: OperationRun, body: DepartmentOutcomeRequest) -> str | None:
    if run.unit != "B":
        return REFUSED_NOT_UNIT_B
    for outcome in body.department_outcomes:
        if outcome.department_id != run.departmentId or outcome.forge_id != run.forgeId:
            return REFUSED_OUTCOME_MISMATCH
    if run.verdict is not None and run.verdict != _TIMEOUT:
        return REFUSED_ALREADY_CLOSED
    return None


async def post_for_office(
    session: AsyncSession, payload: dict[str, Any], origin: dict[str, Any]
) -> PostResult:
    """Record a department outcome for The Office, or refuse it. Audited and committed, either
    way."""
    key = (origin.get("idempotency_key") or "").strip() or None
    raw_ref = payload.get("run_ref")
    run_ref = raw_ref if isinstance(raw_ref, str) and raw_ref else None
    digest = payload_digest(payload)

    def audit(outcome: str, *, refusal: str | None = None, recorded: int = 0) -> None:
        session.add(
            DepartmentOutcomePost(
                runRef=run_ref,
                officeVenture=origin.get("office_venture"),
                officeAgentId=origin.get("office_agent_id"),
                officeTrace=origin.get("office_trace"),
                forgeRequestId=str(origin.get("forge_request_id") or ""),
                idempotencyKey=key,
                payloadDigest=digest,
                outcome=outcome,
                refusal=refusal,
                recorded=recorded,
            )
        )

    async def refuse(code: str, violations: list[dict[str, Any]] | None = None) -> PostResult:
        audit("refused", refusal=code)
        await session.commit()
        return PostResult(reply=None, refusal=code, violations=violations)

    if key is None:
        return await refuse(REFUSED_NO_IDEMPOTENCY_KEY)

    try:
        body = DepartmentOutcomeRequest.model_validate(payload)
    except ValidationError as exc:
        violations = exc.errors(include_url=False, include_context=False)
        return await refuse(REFUSED_PAYLOAD_INVALID, list(violations))

    # Who may post for this run comes before everything about the run - a retry included, so a
    # key cannot be replayed under another venture's header.
    refusal, run = await _lookup_refusal(session, body.run_ref, origin.get("office_venture"))
    if refusal is not None or run is None:
        return await refuse(refusal or REFUSED_UNKNOWN_RUN)

    # A retry is answered from the row the first call wrote, BEFORE the run is checked: the
    # first call closed the run, so the closed-run refusal would otherwise answer every retry.
    prior = await _prior(session, key)
    if prior is not None:
        if prior.payloadDigest != digest:
            return await refuse(REFUSED_KEY_REUSED)
        audit("replayed", recorded=prior.recorded)
        await session.commit()
        return PostResult(reply=_reply(prior.runRef or "", prior.recorded, "replayed"))

    refusal = _run_refusal(run, body)
    if refusal is not None:
        return await refuse(refusal)

    request = GateResultRequest(
        instruction_set_ref=InstructionSetRef(
            forge_id=run.forgeId,
            # A department has no module. Nothing on the department path reads it: the never-do
            # list it keys is for Unit A's coverage check, and the department cert has no module.
            module_id="",
            instruction_version=body.instruction_version,
            forge_api_version=body.forge_api_version,
            # The run's own basis, both sides. The Office minted the ref over this hash, and a
            # department run is not examined against anything that could have moved under it.
            content_hash=run.instructionContentHash,
        ),
        run_content_hash=run.instructionContentHash,
        run_ref=run.runRef,
        sitting=run.sitting,
        agent_outcomes=[],
        department_outcomes=body.department_outcomes,
    )
    recorded = len(body.department_outcomes)
    # Added before the writer runs, so its commit makes the outcome and its audit row permanent
    # together: there is no state in which one exists without the other.
    audit("recorded", recorded=recorded)

    # The writer the battery uses, called the way the battery calls it (`submit_battery_result`).
    # Imported here because a service importing the router at module level is the direction
    # ADR-0050 keeps the request path out of.
    from src.routers.operation import gate_result  # noqa: PLC0415

    try:
        await gate_result(request, session)
    except IntegrityError:
        # A concurrent call with the same key won the unique index. Answer as its retry.
        await session.rollback()
        prior = await _prior(session, key)
        if prior is not None and prior.payloadDigest == digest:
            audit("replayed", recorded=prior.recorded)
            await session.commit()
            return PostResult(reply=_reply(prior.runRef or "", prior.recorded, "replayed"))
        return await refuse(REFUSED_KEY_REUSED)
    return PostResult(reply=_reply(run.runRef, recorded, "recorded"))


__all__ = [
    "NOT_FOUND_REFUSALS",
    "PostResult",
    "REFUSAL_STATUS",
    "REFUSED_ALREADY_CLOSED",
    "REFUSED_ANOTHER_VENTURE",
    "REFUSED_KEY_REUSED",
    "REFUSED_NOT_OFFICE_MINTED",
    "REFUSED_NOT_UNIT_B",
    "REFUSED_NO_IDEMPOTENCY_KEY",
    "REFUSED_NO_VENTURE",
    "REFUSED_OUTCOME_MISMATCH",
    "REFUSED_PAYLOAD_INVALID",
    "REFUSED_UNKNOWN_RUN",
    "payload_digest",
    "post_for_office",
]

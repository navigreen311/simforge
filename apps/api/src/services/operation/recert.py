"""Re-cert triggers + the content-hash VOID rule (Batch 4 + Batch 5).

Every trigger the spec enumerates, each mapping to a DISTINCT state on the operation state machine
(never a low score, never conflated):

  - instruction_version changes            → certs under the prior version → stale_instructions
  - forge_api_version changes (bound mod)  → affected certs → stale_forge  (respecting the cert's
                                             declared version_sensitivity; a PATCH release does not
                                             invalidate unless the cert declared patch-sensitivity)
  - instruction content_hash mismatch      → that cert → revoked + HIGH-severity incident (VOID)
  - new agent into a certified department  → that agent → never_certified for all modules
  - runtime Forge-operation drift          → that agent×module → revoked + remediation note
  - incident traced to Forge misoperation  → agent + department → revoked (BOTH units)
  - operation_rubric_version changes        → operation certs under the prior version → re-cert
                                             (OPERATION unit ONLY; the domain cert table is never
                                             touched — it is a separate table entirely)

The content-hash VOID reuses the existing SoftwareGap/incident mechanism (a P0 gap surfaces through
`incident_report` as a HIGH-severity incident). It is NEVER softened to a warning.

MODELING NOTE (operation_rubric_version re-cert): the foundation's 7-state machine has no dedicated
"rubric superseded" state, and the only LEGAL transitions out of `certified` are stale_instructions
/ stale_forge / revoked. A rubric revision is a re-cert-required, non-destructive event, so it maps
to `stale_instructions` (the nearest legal non-void re-cert state; is_recert_required → True,
is_assignable → False). A dedicated state would be an additive future migration.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.gap import SoftwareGap
from src.models.operation_cert import OperationCertification
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION
from src.services.operation.state_machine import OperationState, is_transition_legal
from src.services.reporter.software_gap import ticket_id

# Default forge-api version sensitivity when a cert declares none: major+minor invalidate, patch
# does NOT (Rev 2 Q4 — a patch bump invalidates only if the cert declared patch-sensitivity).
_DEFAULT_SENSITIVITY: tuple[str, ...] = ("major", "minor")


# --- semver component diff -----------------------------------------------------------------------


def _parse_semver(v: str) -> tuple[int, int, int]:
    parts = (v or "0").split(".")
    nums: list[int] = []
    for i in range(3):
        try:
            nums.append(int(parts[i]) if i < len(parts) else 0)
        except ValueError:
            nums.append(0)
    return nums[0], nums[1], nums[2]


def changed_component(old: str, new: str) -> str | None:
    """The most-significant semver component that changed between `old` and `new`, or None."""
    o, n = _parse_semver(old), _parse_semver(new)
    if o[0] != n[0]:
        return "major"
    if o[1] != n[1]:
        return "minor"
    if o[2] != n[2]:
        return "patch"
    return None


# --- content-hash VOID (reuses the SoftwareGap/incident mechanism) -------------------------------


def is_content_hash_void(declared_hash: str, run_hash: str) -> bool:
    """VOID iff the run's actual instruction content_hash differs from the Office-declared hash.
    Not "questionable" — VOID. Never a warning."""
    return declared_hash != run_hash


async def raise_high_incident(
    session: AsyncSession,
    *,
    forge: str,
    module: str,
    summary: str,
    detail: str,
    run_ref: str,
) -> SoftwareGap:
    """Raise (or increment) a HIGH-severity incident via the existing SoftwareGap mechanism. A P0
    gap surfaces through `incident_report` as a high-severity incident with a blast radius."""
    tid = ticket_id("SF-OPVOID", f"{forge}:{module}:{run_ref}")
    existing = (
        await session.execute(select(SoftwareGap).where(SoftwareGap.ticketId == tid))
    ).scalar_one_or_none()
    if existing is not None:
        existing.occurrenceCount += 1
        existing.lastSeenRunId = run_ref
        return existing
    gap = SoftwareGap(
        ticketId=tid,
        runId=run_ref,
        forge=forge,
        module=module,
        severity="P0",  # → HIGH-severity incident
        summary=summary,
        detail=detail,
        firstSeenRunId=run_ref,
        lastSeenRunId=run_ref,
    )
    session.add(gap)
    return gap


async def void_certification(
    session: AsyncSession,
    *,
    cert: OperationCertification,
    declared_hash: str,
    run_hash: str,
    run_ref: str | None = None,
) -> bool:
    """If the run's content_hash mismatches the declared hash, VOID the cert: state → revoked AND a
    HIGH-severity incident. Returns True if voided. Idempotent-ish (dedup by ticket)."""
    if not is_content_hash_void(declared_hash, run_hash):
        return False
    ref = run_ref or f"op-void-{cert.id}"
    module = cert.moduleId or cert.forgeContext or "unknown"
    cert.state = OperationState.REVOKED
    await raise_high_incident(
        session,
        forge=cert.forgeId,
        module=module,
        summary=f"Operation cert VOID: content_hash mismatch on {cert.forgeId}/{module}",
        detail=(
            f"A certification run executed against content_hash {run_hash!r} but The Office "
            f"declared {declared_hash!r}. Per the content-hash VOID rule the cert is void "
            f"(state=revoked), "
            f"not questionable. cert_id={cert.id}, run_ref={ref}."
        ),
        run_ref=ref,
    )
    await session.commit()
    return True


# --- stale triggers ------------------------------------------------------------------------------


async def _certified_unit_a(
    session: AsyncSession, *, forge_id: str, module_id: str
) -> list[OperationCertification]:
    rows = (
        (
            await session.execute(
                select(OperationCertification).where(
                    OperationCertification.unitType == "agent_operation",
                    OperationCertification.forgeId == forge_id,
                    OperationCertification.moduleId == module_id,
                    OperationCertification.state == OperationState.CERTIFIED.value,
                )
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def mark_stale_on_instruction_change(
    session: AsyncSession, *, forge_id: str, module_id: str, new_instruction_version: str
) -> list[OperationCertification]:
    """Certs earned under a prior instruction_version → stale_instructions (re-cert required)."""
    affected: list[OperationCertification] = []
    for cert in await _certified_unit_a(session, forge_id=forge_id, module_id=module_id):
        if cert.instructionVersion != new_instruction_version and is_transition_legal(
            cert.state, OperationState.STALE_INSTRUCTIONS
        ):
            cert.state = OperationState.STALE_INSTRUCTIONS
            affected.append(cert)
    await session.commit()
    return affected


async def mark_stale_on_forge_change(
    session: AsyncSession, *, forge_id: str, module_id: str, new_forge_api_version: str
) -> list[OperationCertification]:
    """Certs on a bound module whose declared version_sensitivity covers the changed semver
    component → stale_forge. A patch bump does NOT invalidate unless the cert declared
    patch-sensitivity (Rev 2 Q4)."""
    affected: list[OperationCertification] = []
    for cert in await _certified_unit_a(session, forge_id=forge_id, module_id=module_id):
        comp = changed_component(cert.forgeApiVersion, new_forge_api_version)
        if comp is None:
            continue
        sens = (cert.versionSensitivity or {}).get(module_id)
        sensitive_components = tuple(sens) if sens else _DEFAULT_SENSITIVITY
        if comp in sensitive_components and is_transition_legal(
            cert.state, OperationState.STALE_FORGE
        ):
            cert.state = OperationState.STALE_FORGE
            affected.append(cert)
    await session.commit()
    return affected


# --- never_certified / revoke / rubric triggers --------------------------------------------------


async def mark_never_certified_for_new_agent(
    session: AsyncSession,
    *,
    agent_id: str,
    forge_id: str,
    modules: list[str],
) -> list[OperationCertification]:
    """A new agent produced into a certified department starts never_certified for ALL modules — it
    inherits the department's context (Unit B) but NOT operation competence (Unit A).
    never_certified is a real absence, distinct from failed and from a low score."""
    created: list[OperationCertification] = []
    for module_id in modules:
        cert = OperationCertification(
            unitType="agent_operation",
            state=OperationState.NEVER_CERTIFIED.value,
            forgeId=forge_id,
            instructionVersion="",  # never run → no version earned under yet
            forgeApiVersion="",
            instructionContentHash="",
            operationRubricVersion=OPERATION_RUBRIC_VERSION,
            agentId=agent_id,
            moduleId=module_id,
            functionsCertified=0,
            functionsInModule=None,  # unknown until a battery runs
        )
        session.add(cert)
        created.append(cert)
    await session.commit()
    return created


async def revoke_on_runtime_drift(
    session: AsyncSession, *, agent_id: str, module_id: str
) -> list[OperationCertification]:
    """Runtime Forge-operation drift on a certified agent×module → revoked + remediation note."""
    rows = (
        (
            await session.execute(
                select(OperationCertification).where(
                    OperationCertification.unitType == "agent_operation",
                    OperationCertification.agentId == agent_id,
                    OperationCertification.moduleId == module_id,
                    OperationCertification.state == OperationState.CERTIFIED.value,
                )
            )
        )
        .scalars()
        .all()
    )
    for cert in rows:
        cert.state = OperationState.REVOKED
        modes = list(cert.failureModesObserved or [])
        modes.append("runtime_operation_drift:remediation_required")
        cert.failureModesObserved = modes
    await session.commit()
    return list(rows)


async def revoke_on_incident(
    session: AsyncSession, *, agent_id: str, department_id: str, forge_id: str
) -> list[OperationCertification]:
    """An incident traced to Forge misoperation revokes BOTH units: the agent's Unit A and the
    department's Unit B for that forge."""
    rows = (
        (
            await session.execute(
                select(OperationCertification).where(
                    OperationCertification.forgeId == forge_id,
                    OperationCertification.state == OperationState.CERTIFIED.value,
                )
            )
        )
        .scalars()
        .all()
    )
    affected: list[OperationCertification] = []
    for cert in rows:
        is_agent_unit = cert.unitType == "agent_operation" and cert.agentId == agent_id
        is_dept_unit = (
            cert.unitType == "department_context" and cert.departmentId == department_id
        )
        if is_agent_unit or is_dept_unit:
            cert.state = OperationState.REVOKED
            affected.append(cert)
    await session.commit()
    return affected


async def recert_on_operation_rubric_change(
    session: AsyncSession, *, new_operation_rubric_version: str = OPERATION_RUBRIC_VERSION
) -> list[OperationCertification]:
    """An operation_rubric_version change re-certs OPERATION units earned under the prior version —
    and ONLY operation units. The domain cert table (AgentCert/DeptCert) is a different table and is
    never touched here. See the module MODELING NOTE for the stale_instructions state reuse."""
    rows = (
        (
            await session.execute(
                select(OperationCertification).where(
                    OperationCertification.state == OperationState.CERTIFIED.value,
                )
            )
        )
        .scalars()
        .all()
    )
    affected: list[OperationCertification] = []
    for cert in rows:
        if cert.operationRubricVersion != new_operation_rubric_version and is_transition_legal(
            cert.state, OperationState.STALE_INSTRUCTIONS
        ):
            cert.state = OperationState.STALE_INSTRUCTIONS
            affected.append(cert)
    await session.commit()
    return affected


__all__ = [
    "changed_component",
    "is_content_hash_void",
    "raise_high_incident",
    "void_certification",
    "mark_stale_on_instruction_change",
    "mark_stale_on_forge_change",
    "mark_never_certified_for_new_agent",
    "revoke_on_runtime_drift",
    "revoke_on_incident",
    "recert_on_operation_rubric_change",
]

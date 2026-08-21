"""Operation-cert gating (Batch 5). SimForge is the source of truth for cert states; The Office
consumes these to gate shift assignment.

ASSIGNMENT RULE (both required):
    An agent is assignable to a shift requiring module M only if
      (1) the agent holds a CURRENT (state=certified) Unit A cert for M, AND
      (2) the agent's department holds a CURRENT Unit B cert for M's Forge in that venture context.
    Unit B is NECESSARY but NOT SUFFICIENT: a new agent in a certified department starts
    never_certified and must earn A. Unit A without department B is NOT assignable — competence
    without context is not clearance.

PROMOTION vs ASSIGNMENT (Rev 2 §6.3 — do NOT conflate; this engine only REPORTS):
    An operation failure blocks that agent×module ASSIGNMENT. It blocks VILLAGE PROMOTION only when
    NO candidate agent holds a current cert for a module the workflow requires (a venture with three
    certified agents + one uncertified is promotable; the uncertified one just is not assignable).
    SimForge reports per-agent state accurately; The Office enforces the promotion/assignment
    distinction. `module_has_any_certified_agent` is a REPORTING helper for that decision — it does
    NOT enforce a promotion gate here.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.department import Department
from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.operation_cert import OperationCertification
from src.services.operation.state_machine import OperationState, is_assignable


@dataclass(frozen=True)
class AssignabilityResult:
    assignable: bool
    agent_id: str
    module_id: str
    forge_id: str | None
    venture_context: str | None
    unit_a_state: str  # certified | stale_* | failed | never_certified | revoked | in_training
    unit_b_state: str
    reason: str


async def _latest_unit_a(
    session: AsyncSession, *, agent_id: str, module_id: str
) -> OperationCertification | None:
    rows = (
        (
            await session.execute(
                select(OperationCertification)
                .where(
                    OperationCertification.unitType == "agent_operation",
                    OperationCertification.agentId == agent_id,
                    OperationCertification.moduleId == module_id,
                )
                .order_by(OperationCertification.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )
    return rows[0] if rows else None


async def _latest_unit_b(
    session: AsyncSession,
    *,
    dept_identifiers: set[str],
    forge_id: str,
    venture_context: str | None,
) -> OperationCertification | None:
    q = select(OperationCertification).where(
        OperationCertification.unitType == "department_context",
        OperationCertification.forgeId == forge_id,
        OperationCertification.departmentId.in_(dept_identifiers),
    )
    if venture_context is not None:
        q = q.where(OperationCertification.ventureContext == venture_context)
    rows = (
        (await session.execute(q.order_by(OperationCertification.createdAt.desc())))
        .scalars()
        .all()
    )
    return rows[0] if rows else None


async def _resolve_department(
    session: AsyncSession, agent_id: str
) -> tuple[Agent | None, set[str]]:
    """Return the agent and the set of identifiers a Unit B departmentId might be stored as
    (Department.id and villageKey), so gating is robust to either convention."""
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == agent_id))
    ).scalar_one_or_none()
    if agent is None:
        return None, set()
    idents: set[str] = {agent.departmentId}
    dept = (
        await session.execute(select(Department).where(Department.id == agent.departmentId))
    ).scalar_one_or_none()
    if dept is not None:
        idents.add(dept.villageKey)
    return agent, idents


async def agent_module_assignability(
    session: AsyncSession,
    *,
    agent_id: str,
    module_id: str,
    venture_context: str | None = None,
    forge_id: str | None = None,
) -> AssignabilityResult:
    """Compute assignability for agent × module, requiring BOTH a current Unit A and Unit B."""
    unit_a = await _latest_unit_a(session, agent_id=agent_id, module_id=module_id)
    # A missing Unit A row is never_certified (a real absence), NOT a low score or a failure.
    unit_a_state = unit_a.state if unit_a else OperationState.NEVER_CERTIFIED.value
    resolved_forge = forge_id or (unit_a.forgeId if unit_a else None)
    if resolved_forge is None:
        # A new agent has no Unit A to name the forge; resolve the module's forge from the bound
        # instruction set so Unit B can still be evaluated (module → forge is a real mapping).
        iset = (
            await session.execute(
                select(ForgeInstructionSet.forgeId).where(
                    ForgeInstructionSet.moduleId == module_id
                )
            )
        ).first()
        resolved_forge = iset[0] if iset else None

    _agent, dept_idents = await _resolve_department(session, agent_id)

    unit_b_state = OperationState.NEVER_CERTIFIED.value
    if resolved_forge and dept_idents:
        unit_b = await _latest_unit_b(
            session,
            dept_identifiers=dept_idents,
            forge_id=resolved_forge,
            venture_context=venture_context,
        )
        if unit_b is not None:
            unit_b_state = unit_b.state

    a_ok = is_assignable(unit_a_state)
    b_ok = is_assignable(unit_b_state)
    assignable = a_ok and b_ok

    if assignable:
        reason = "assignable: current Unit A (agent) and current Unit B (department context)"
    elif not a_ok and not b_ok:
        reason = f"not assignable: Unit A is {unit_a_state} and Unit B is {unit_b_state}"
    elif not a_ok:
        reason = (
            f"not assignable: agent Unit A is {unit_a_state} "
            f"(Unit B {unit_b_state} is necessary but not sufficient)"
        )
    else:
        reason = f"not assignable: department Unit B is {unit_b_state} (agent Unit A is certified)"

    return AssignabilityResult(
        assignable=assignable,
        agent_id=agent_id,
        module_id=module_id,
        forge_id=resolved_forge,
        venture_context=venture_context,
        unit_a_state=unit_a_state,
        unit_b_state=unit_b_state,
        reason=reason,
    )


async def module_has_any_certified_agent(
    session: AsyncSession, *, forge_id: str, module_id: str
) -> bool:
    """REPORTING helper for the promotion-vs-assignment distinction (Rev 2 §6.3). True if ANY agent
    holds a current Unit A cert for this module. Does NOT enforce a promotion gate — The Office
    decides promotion; SimForge only reports."""
    row = (
        await session.execute(
            select(OperationCertification.id).where(
                OperationCertification.unitType == "agent_operation",
                OperationCertification.forgeId == forge_id,
                OperationCertification.moduleId == module_id,
                OperationCertification.state == OperationState.CERTIFIED.value,
            )
        )
    ).first()
    return row is not None


async def agent_operation_states(
    session: AsyncSession, *, agent_id: str
) -> list[OperationCertification]:
    """All Unit A certs for an agent (latest-first) — per-agent operation view (module × state ×
    version stamps × denominator)."""
    rows = (
        (
            await session.execute(
                select(OperationCertification)
                .where(
                    OperationCertification.unitType == "agent_operation",
                    OperationCertification.agentId == agent_id,
                )
                .order_by(OperationCertification.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


__all__ = [
    "AssignabilityResult",
    "agent_module_assignability",
    "module_has_any_certified_agent",
    "agent_operation_states",
]

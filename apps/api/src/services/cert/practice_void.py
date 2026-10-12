"""Void the certificates issued from practice runs (ADR-0158).

Ivan Green's ruling, 2026-10-12: a certificate issued from practice runs is not a certification
(ADR-0157 ruling 1), whatever model ran. He named nine: David Kim's seven AgentCerts and two
voiceforge OperationCertifications. They are listed here by id, with the state each held when the
ruling was given, so the void touches exactly those and refuses if any has moved.

Append-only:
- an AgentCert gets a `revoked` CertLifecycleEvent (`revoke_agent_cert`, with `skip_demotion=True`);
- an OperationCertification gets a `revoked` OperationCertificationEvent (`void.py`).

No stacked demotions. Each revoke would drop the agent one level; instead the level is set once,
explicitly, to the floor (`L1`, Observe only), and only if the agent holds no valid certification
afterwards. `L1` is where an agent with no certification sits: new agents start there and earn
higher levels through certification (`autonomy_ladder.FLOOR`).

`plan` only reads. `apply` writes, and only for an enrolled operator who authenticates with their
own credential (ADR-0159, the ADR-0154 operators). A typed name is not enough. Every attempt is a
`PartitionOperatorEvent` with act `void`: done, or refused with its code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert
from src.models.operation_cert import OperationCertification
from src.services.cert.autonomy_ladder import FLOOR, record_transition
from src.services.cert.registry import revoke_agent_cert
from src.services.operation.partition_operators import audit, authenticate, refuse
from src.services.operation.state_machine import OperationState
from src.services.operation.void import revoke_operation_certification

REASON = (
    "VOID - ruling of Ivan Green, 2026-10-12 (ADR-0157 ruling 1, ADR-0158): issued from practice "
    "runs. A certificate issued from practice runs is not a certification, whatever model ran."
)
LEVEL_REASON = (
    "ADR-0158: every certification this agent held was voided as issued from practice runs; an "
    "agent with no valid certification sits at the floor (L1, Observe only). Set once, explicitly."
)

AGENT = "david_kim"

#: (AgentCert id, forge capability, status when the ruling was given)
AGENT_CERTS: tuple[tuple[str, str, str], ...] = (
    ("01M03QY839Y9DAH38ENRPWG5T6", "cre-forge.deals.title", "active"),
    ("01KY37BAS7KG2TECMDKQEGG822", "capitalforge.demo.train_1784667286", "suspended"),
    ("01KY36X5H6SJ8Y93JDMFN00CTM", "capitalforge.emd.release", "suspended"),
    ("01KY1JZ1FTFRVDY5BR33E6GWA5", "cre-forge.call_center.outbound_seller_outreach", "suspended"),
    ("01KY1KB9NXYN1PGQAP07X601HB", "funnelforge.sequences.trigger", "suspended"),
    ("01KY2QTA19RSF8QY2ABH85TJ2Z", "vaf.doc_vault.retrieve", "suspended"),
    ("01KY2SCYEPKWYWRSJMR120NASZ", "voiceforge.call_center.inbound", "suspended"),
)

#: (OperationCertification id, what it is, state when the ruling was given)
OPERATION_CERTS: tuple[tuple[str, str, str], ...] = (
    ("01M128NV2M6CKS5MDA997S1J65", "Unit A sara_lopez x voiceforge/call_flow", "certified"),
    ("01M0KHDK94X4EVD1BCCK63TWS4", "Unit B voiceforge dept (medlink-pro)", "certified"),
)


#: The audit act, and the refusal code when the plan refuses after the operator authenticated.
ACT = "void"
REFUSED_PLAN = "void_plan_refused"


class VoidRefused(Exception):
    """A target is missing or has moved since the ruling. Nothing is written."""


@dataclass
class Step:
    kind: str  # agent_cert | operation_cert | autonomy
    target: str
    label: str
    before: str
    after: str
    appends: str


@dataclass
class Plan:
    steps: list[Step] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


async def _david(session: AsyncSession) -> Agent:
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == AGENT))
    ).scalar_one_or_none()
    if agent is None:
        raise VoidRefused(f"agent {AGENT} not found")
    return agent


async def _still_certified_elsewhere(
    session: AsyncSession, agent: Agent, voiding: set[str]
) -> list[str]:
    """The agent's certifications that survive the void: an active AgentCert not being voided, or
    an OperationCertification whose LATEST row for its module is `certified`."""
    held = [
        f"AgentCert {c.id} {c.forgeCap}"
        for c in (
            await session.execute(
                select(AgentCert).where(AgentCert.agentId == agent.id, AgentCert.status == "active")
            )
        )
        .scalars()
        .all()
        if c.id not in voiding
    ]
    latest: dict[str, OperationCertification] = {}
    rows = (
        (
            await session.execute(
                select(OperationCertification)
                .where(
                    OperationCertification.unitType == "agent_operation",
                    OperationCertification.agentId == agent.id,
                )
                .order_by(OperationCertification.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        latest.setdefault(f"{row.forgeId}/{row.moduleId}", row)
    held += [
        f"OperationCertification {row.id} {key}"
        for key, row in latest.items()
        if row.state == OperationState.CERTIFIED.value and row.id not in voiding
    ]
    return held


async def plan(session: AsyncSession) -> Plan:
    """What `apply` would do. Reads only. Raises VoidRefused if any target moved."""
    out = Plan()
    for cert_id, cap, expected in AGENT_CERTS:
        cert = (
            await session.execute(select(AgentCert).where(AgentCert.id == cert_id))
        ).scalar_one_or_none()
        if cert is None:
            raise VoidRefused(f"AgentCert {cert_id} not found")
        if cert.status == "revoked":
            out.skipped.append(f"AgentCert {cert_id} already revoked")
            continue
        if cert.status != expected or cert.forgeCap != cap:
            raise VoidRefused(
                f"AgentCert {cert_id} is {cert.status} {cert.forgeCap}, expected {expected} {cap}"
            )
        out.steps.append(
            Step("agent_cert", cert_id, cap, cert.status, "revoked", "CertLifecycleEvent revoked")
        )
    for cert_id, label, expected in OPERATION_CERTS:
        op = (
            await session.execute(
                select(OperationCertification).where(OperationCertification.id == cert_id)
            )
        ).scalar_one_or_none()
        if op is None:
            raise VoidRefused(f"OperationCertification {cert_id} not found")
        if op.state == OperationState.REVOKED.value:
            out.skipped.append(f"OperationCertification {cert_id} already revoked")
            continue
        if op.state != expected:
            raise VoidRefused(
                f"OperationCertification {cert_id} is {op.state}, expected {expected}"
            )
        out.steps.append(
            Step(
                "operation_cert",
                cert_id,
                label,
                op.state,
                "revoked",
                "OperationCertificationEvent revoked",
            )
        )

    agent = await _david(session)
    voiding = {cert_id for cert_id, _, _ in AGENT_CERTS}
    surviving = await _still_certified_elsewhere(session, agent, voiding)
    if surviving:
        raise VoidRefused(
            f"{AGENT} keeps a certification, so the floor does not apply: {surviving}"
        )
    if agent.currentAutonomyLevel != FLOOR:
        out.steps.append(
            Step(
                "autonomy",
                AGENT,
                "no valid certification",
                agent.currentAutonomyLevel,
                FLOOR,
                "AutonomyEvent (one)",
            )
        )
    return out


async def apply(session: AsyncSession, *, operator_name: str, credential: str) -> Plan:
    """Write the plan, signed by an enrolled operator (ADR-0159).

    Authenticates first: an unknown name or a wrong credential raises `OperatorRefused`, audited,
    and nothing is read or written. Then re-plans, so a target that moved since the dry run refuses
    here, also audited. The actor on every event is the operator's name and id, as enrolled.
    """
    operator = await authenticate(session, operator_name, credential, act=ACT)
    actor = f"{operator.name} (operator {operator.id})"
    try:
        the_plan = await plan(session)
    except VoidRefused:
        await refuse(
            session,
            "the void plan was refused",
            REFUSED_PLAN,
            act=ACT,
            claimed_name=operator_name,
            operator_id=operator.id,
        )
        raise
    for step in the_plan.steps:
        if step.kind == "agent_cert":
            # Commits per cert and publishes to the PEP; re-running skips what is revoked.
            await revoke_agent_cert(session, step.target, REASON, actor, skip_demotion=True)
    for step in the_plan.steps:
        if step.kind == "operation_cert":
            op = (
                await session.execute(
                    select(OperationCertification).where(OperationCertification.id == step.target)
                )
            ).scalar_one()
            await revoke_operation_certification(session, op, reason=REASON, actor=actor)
    for step in the_plan.steps:
        if step.kind == "autonomy":
            await record_transition(
                session, await _david(session), FLOOR, LEVEL_REASON, triggered_by=actor
            )
    audit(session, act=ACT, claimed_name=operator_name, outcome="done", operator_id=operator.id)
    await session.commit()
    return the_plan

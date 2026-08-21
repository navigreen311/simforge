"""Composed read-views for the operation-cert UI (Batch 6).

The UI shows the DOMAIN cert and the OPERATION cert side by side — two records, two denominators,
two version stamps, never one merged number. These builders assemble exactly that: per agent
operation cert (Unit A) they attach a DomainCertRef (the agent's domain cert, its OWN
state/tier/version), plus coverage, capacity (§8), and Unit-B department-context views. Labels are
humanized from ids (no forge label registry yet) — a raw id is never shown as a friendly name.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert
from src.models.department import Department
from src.models.operation_cert import OperationCertification
from src.services.operation.rubric import OPERATION_RUBRIC_VERSION
from src.services.operation.state_machine import OperationState, is_assignable

# The domain rubric is the established 8-dimension rubric; its version is stamped SEPARATELY from
# the operation rubric so the two are never conflated. (No shared constant exists; domain stamp.)
DOMAIN_RUBRIC_VERSION = "1.0.0"
DOMAIN_RUBRIC_DIMENSIONS = 8
THIN_COVERAGE_THRESHOLD = 0.5


def _humanize(raw: str | None) -> str:
    if not raw:
        return "—"
    return raw.replace("_", " ").replace("-", " ").replace(".", " ").strip().title()


def _agent_operation_cert(c: OperationCertification, village_id: str, name: str) -> dict:
    return {
        "agent_village_id": village_id,
        "agent_name": name,
        "forge_id": c.forgeId,
        "forge_label": _humanize(c.forgeId),
        "module_id": c.moduleId or "",
        "module_label": _humanize(c.moduleId),
        "state": c.state,
        "max_certified_trust_tier": c.maxCertifiedTrustTier,
        "functions_certified": c.functionsCertified or 0,
        "functions_in_module": c.functionsInModule or 0,  # DENOMINATOR
        "operation_rubric_results": c.operationRubricResults or [],  # NAMED LIST
        "rubric_dimension_spread": c.rubricDimensionSpread,
        "per_scenario_class_results": [
            {"scenario_class": k, "verdict": v} for k, v in (c.perScenarioClass or {}).items()
        ],
        "failure_modes_observed": c.failureModesObserved or [],
        "instruction_version": c.instructionVersion,
        "forge_api_version": c.forgeApiVersion,
        "instruction_content_hash": c.instructionContentHash,
        "operation_rubric_version": c.operationRubricVersion,
        "expires_at": c.expiresAt.isoformat() if c.expiresAt else None,
        "reviewed_by": c.reviewedBy,
        "reviewed_at": c.reviewedAt.isoformat() if c.reviewedAt else None,
    }


def _domain_ref(cert: AgentCert | None) -> dict:
    """The domain cert shown ALONGSIDE — its own record, its own version stamp, never merged."""
    if cert is None:
        return {
            "present": False,
            "state": None,
            "tier": None,
            "dimensions_passed": None,
            "dimensions_total": None,
            "rubric_version": None,
            "issued_at": None,
            "expires_at": None,
        }
    return {
        "present": True,
        "state": cert.status,
        "tier": cert.tier,
        "dimensions_passed": None,  # not stored per-cert; shown as unknown, never faked as a number
        "dimensions_total": DOMAIN_RUBRIC_DIMENSIONS,
        "rubric_version": DOMAIN_RUBRIC_VERSION,  # DOMAIN stamp — separate from operation
        "issued_at": cert.issuedAt.isoformat() if cert.issuedAt else None,
        "expires_at": cert.expiresAt.isoformat() if cert.expiresAt else None,
    }


async def _agents(session: AsyncSession) -> dict[str, Agent]:
    return {a.id: a for a in (await session.execute(select(Agent))).scalars().all()}


async def side_by_side(session: AsyncSession) -> dict:
    agents = await _agents(session)
    # Active domain cert per agent (any forge cap) — the record paired beside the operation one.
    domain_by_agent: dict[str, AgentCert] = {}
    for dc in (await session.execute(select(AgentCert))).scalars().all():
        if dc.status == "active" and dc.agentId not in domain_by_agent:
            domain_by_agent[dc.agentId] = dc

    unit_a = (
        (
            await session.execute(
                select(OperationCertification)
                .where(OperationCertification.unitType == "agent_operation")
                .order_by(OperationCertification.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )
    items: list[dict] = []
    for c in unit_a:
        agent = agents.get(c.agentId or "")
        village_id = agent.villageAgentId if agent else (c.agentId or "unknown")
        name = agent.name if agent else (c.agentId or "unknown")
        items.append(
            {
                "agent_village_id": village_id,
                "agent_name": name,
                "capability_label": _humanize(c.moduleId),
                "module_id": c.moduleId or "",
                "forge_id": c.forgeId,
                "forge_label": _humanize(c.forgeId),
                "domain": _domain_ref(domain_by_agent.get(c.agentId or "")),
                "operation": _agent_operation_cert(c, village_id, name),
            }
        )
    return {
        "items": items,
        "total": len(items),
        "operation_rubric_version": OPERATION_RUBRIC_VERSION,
        "domain_rubric_version": DOMAIN_RUBRIC_VERSION,
    }


async def coverage(session: AsyncSession) -> dict:
    unit_a = (
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
    by_forge: dict[str, dict] = {}
    for c in unit_a:
        forge = by_forge.setdefault(c.forgeId, {"forge_id": c.forgeId, "modules": {}})
        mod = c.moduleId or "unknown"
        m = forge["modules"].setdefault(
            mod,
            {"module_id": mod, "functions_in_module": c.functionsInModule or 0, "certified": 0},
        )
        if c.functionsInModule:
            m["functions_in_module"] = c.functionsInModule
        if c.state == OperationState.CERTIFIED.value:
            m["certified"] = max(m["certified"], c.functionsCertified or 0)
    forges = []
    for forge_id, f in sorted(by_forge.items()):
        modules = []
        for mod in sorted(f["modules"].values(), key=lambda x: x["module_id"]):
            denom = mod["functions_in_module"] or 0
            covered = mod["certified"]
            thin = denom == 0 or (covered / denom) < THIN_COVERAGE_THRESHOLD
            modules.append(
                {
                    "module_id": mod["module_id"],
                    "module_label": _humanize(mod["module_id"]),
                    "functions_covered": covered,
                    "functions_in_module": denom,
                    "thin": thin,
                }
            )
        covered_mods = sum(1 for m in modules if not m["thin"])
        forges.append(
            {
                "forge_id": forge_id,
                "forge_label": _humanize(forge_id),
                "modules_covered": covered_mods,
                "modules_in_forge": len(modules),  # modules SEEN (no forge registry yet)
                "modules_uncovered": [m["module_id"] for m in modules if m["thin"]],
                "modules": modules,
                "operation_rubric_version": OPERATION_RUBRIC_VERSION,
            }
        )
    return {"forges": forges, "thin_coverage_threshold": THIN_COVERAGE_THRESHOLD}


async def capacity(session: AsyncSession) -> dict:
    unit_a = (
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
    by_module: dict[str, dict] = {}
    for c in unit_a:
        mod = c.moduleId or "unknown"
        m = by_module.setdefault(
            mod,
            {
                "module_id": mod,
                "module_label": _humanize(mod),
                "forge_label": _humanize(c.forgeId),
                "certified": 0,
                "never_certified": 0,
                "in_training": 0,
            },
        )
        if c.state == OperationState.CERTIFIED.value:
            m["certified"] += 1
        elif c.state == OperationState.NEVER_CERTIFIED.value:
            m["never_certified"] += 1
        elif c.state == OperationState.IN_TRAINING.value:
            m["in_training"] += 1
    modules = []
    tot_free = tot_alloc = tot_produced = 0
    for m in sorted(by_module.values(), key=lambda x: x["module_id"]):
        produced = m["never_certified"] + m["in_training"]
        # certified_free / certified_allocated are the Office's allocator concern; SimForge only
        # knows its certs are certified — reports them "free" and allocation (Office-owned) as 0.
        modules.append(
            {
                "module_id": m["module_id"],
                "module_label": m["module_label"],
                "forge_label": m["forge_label"],
                "certified_free": m["certified"],  # Office-owned allocator number (SimForge view)
                "certified_allocated": 0,  # Office-owned; SimForge does not track allocation
                "produced_not_certified": produced,  # SimForge-owned
                "never_certified": m["never_certified"],
                "in_training": m["in_training"],
            }
        )
        tot_free += m["certified"]
        tot_produced += produced
    return {
        "modules": modules,
        "totals": {
            "certified_free": tot_free,
            "certified_allocated": tot_alloc,
            "produced_not_certified": tot_produced,
        },
    }


async def dept_context(session: AsyncSession) -> dict:
    depts = {
        d.id: d.villageKey for d in (await session.execute(select(Department))).scalars().all()
    }
    unit_b = (
        (
            await session.execute(
                select(OperationCertification).where(
                    OperationCertification.unitType == "department_context"
                )
            )
        )
        .scalars()
        .all()
    )
    items = [
        {
            "department_id": c.departmentId or "",
            "department_key": depts.get(c.departmentId or "", c.departmentId or "unknown"),
            "forge_id": c.forgeId,
            "forge_label": _humanize(c.forgeId),
            "forge_context": c.forgeContext or "",
            "venture_context": c.ventureContext or "",
            "state": c.state,
            "assignable": is_assignable(c.state),
            "escalation_path_verified": bool(c.escalationPathVerified),
            "compliance_coupling_verified": bool(c.complianceCouplingVerified),
            "instruction_version": c.instructionVersion,
            "forge_api_version": c.forgeApiVersion,
            "operation_rubric_version": c.operationRubricVersion,
            "reviewed_by": c.reviewedBy,
            "reviewed_at": c.reviewedAt.isoformat() if c.reviewedAt else None,
        }
        for c in unit_b
    ]
    return {"items": items, "total": len(items)}

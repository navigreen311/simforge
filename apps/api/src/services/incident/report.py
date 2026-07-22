"""Incident Command report (ADR-0040).

The v1.2 on-call view: one place that answers "what is wrong right now, and how big is the blast
radius?" It does not invent a new incident store — it *derives* current incidents from the signals
the platform already records: emergency safe mode, governance-invalidated certs (revoked/suspended),
open high-severity software gaps, and a breached cost cap. Each incident carries its blast radius —
the agents, forge capabilities, and departments it touches.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert
from src.models.department import Department
from src.models.gap import SoftwareGap
from src.services.budget import budget_status
from src.services.governance.safe_mode import safe_mode

# severity → rank for sorting/counting (higher = worse)
_RANK = {"critical": 3, "high": 2, "medium": 1}


async def _cert_blast_radius(session: AsyncSession, certs: list[AgentCert]) -> dict:
    agent_ids = {c.agentId for c in certs}
    agents = (
        (await session.execute(select(Agent).where(Agent.id.in_(agent_ids)))).scalars().all()
        if agent_ids
        else []
    )
    dept_ids = {a.departmentId for a in agents}
    depts = (
        (await session.execute(select(Department).where(Department.id.in_(dept_ids))))
        .scalars()
        .all()
        if dept_ids
        else []
    )
    return {
        "agents": sorted({a.villageAgentId for a in agents}),
        "forge_caps": sorted({c.forgeCap for c in certs}),
        "departments": sorted({d.name for d in depts}),
    }


async def incident_report(session: AsyncSession) -> dict:
    """Assemble the current incident list + blast radius from live platform signals."""
    incidents: list[dict] = []

    # 1. Emergency safe mode.
    sm = safe_mode.status()
    if sm["active"]:
        incidents.append(
            {
                "kind": "safe_mode",
                "severity": "critical",
                "summary": f"Safe mode active: {sm['reason'] or 'emergency halt'}",
                "count": 1,
                "blast_radius": {"agents": [], "forge_caps": [], "departments": sm["domains"]},
            }
        )

    # 2. Governance-invalidated certs (revoked = high, suspended = medium).
    invalidated = (
        (
            await session.execute(
                select(AgentCert).where(AgentCert.status.in_(("revoked", "suspended")))
            )
        )
        .scalars()
        .all()
    )
    for status_val, severity in (("revoked", "high"), ("suspended", "medium")):
        group = [c for c in invalidated if c.status == status_val]
        if group:
            incidents.append(
                {
                    "kind": f"certs_{status_val}",
                    "severity": severity,
                    "summary": f"{len(group)} cert(s) {status_val}",
                    "count": len(group),
                    "blast_radius": await _cert_blast_radius(session, group),
                }
            )

    # 3. Open high-severity software gaps (P0 = high, P1 = medium).
    open_gaps = (
        (await session.execute(select(SoftwareGap).where(SoftwareGap.status == "open")))
        .scalars()
        .all()
    )
    for sev, severity in (("P0", "high"), ("P1", "medium")):
        gap_group = [g for g in open_gaps if g.severity == sev]
        if gap_group:
            incidents.append(
                {
                    "kind": f"gaps_{sev.lower()}",
                    "severity": severity,
                    "summary": f"{len(gap_group)} open {sev} software gap(s)",
                    "count": len(gap_group),
                    "blast_radius": {
                        "agents": [],
                        "forge_caps": sorted({g.forge for g in gap_group}),
                        "departments": [],
                    },
                }
            )

    # 4. Breached cost cap.
    budget = await budget_status(session)
    for mode, info in budget["modes"].items():
        if info["exceeded"]:
            spent, cap = info["spent_usd"], info["cap_usd"]
            incidents.append(
                {
                    "kind": f"budget_{mode}",
                    "severity": "high",
                    "summary": f"{mode} budget exceeded (${spent:.2f}/${cap:.2f})",
                    "count": 1,
                    "blast_radius": {"agents": [], "forge_caps": [], "departments": []},
                }
            )

    incidents.sort(key=lambda i: _RANK.get(i["severity"], 0), reverse=True)
    counts = {sev: sum(1 for i in incidents if i["severity"] == sev) for sev in _RANK}
    return {
        "safe_mode": sm,
        "budget": budget,
        "incidents": incidents,
        "counts": counts,
        "total_incidents": len(incidents),
        "status": "ok" if not incidents else ("critical" if counts["critical"] else "degraded"),
    }

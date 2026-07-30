"""Dashboard aggregates router (blueprint §C.3.10)."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.agent import Agent
from src.models.cert import AgentCert
from src.models.gap import SoftwareGap, VillageOSGap
from src.models.run import Run
from src.utils.time import utcnow

router = APIRouter()

# Autonomy ladder rank (L1 lowest → L5 full). L3+ means "may execute" and REQUIRES a live cert.
_LADDER_RANK = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}


@router.get("/throughput", dependencies=[Depends(require_role("viewer"))])
async def throughput(session: AsyncSession = Depends(get_session)) -> dict:
    by_status = (await session.execute(select(Run.status, func.count()).group_by(Run.status))).all()
    totals = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Run.tokensUsed), 0),
                func.coalesce(func.sum(Run.costUsd), 0.0),
            )
        )
    ).one()
    return {
        "runs_by_status": {s: c for s, c in by_status},
        "total_runs": totals[0],
        "total_tokens": int(totals[1]),
        "total_cost_usd": float(totals[2]),
    }


@router.get("/readiness-matrix", dependencies=[Depends(require_role("viewer"))])
async def readiness_matrix(session: AsyncSession = Depends(get_session)) -> dict:
    certs = (await session.execute(select(AgentCert))).scalars().all()
    agents = {
        a.id: a.villageAgentId for a in (await session.execute(select(Agent))).scalars().all()
    }
    caps = sorted({c.forgeCap for c in certs})
    cells = [
        {
            "agent": agents.get(c.agentId, c.agentId),
            "forge_cap": c.forgeCap,
            "tier": c.tier,
            "status": c.status,
        }
        for c in certs
    ]
    return {"forge_caps": caps, "cells": cells, "total_certs": len(certs)}


@router.get("/summary", dependencies=[Depends(require_role("viewer"))])
async def summary(session: AsyncSession = Depends(get_session)) -> dict:
    async def _count(model, *where) -> int:
        stmt = select(func.count()).select_from(model)
        for w in where:
            stmt = stmt.where(w)
        return (await session.execute(stmt)).scalar_one()

    return {
        "agents": await _count(Agent),
        "runs": await _count(Run),
        "active_certs": await _count(AgentCert, AgentCert.status == "active"),
        "issued_certs": await _count(AgentCert),
        "open_software_gaps": await _count(SoftwareGap, SoftwareGap.status == "open"),
        "open_village_os_gaps": await _count(VillageOSGap, VillageOSGap.status == "open"),
    }


async def _active_certs_by_agent(session: AsyncSession) -> dict[str, int]:
    rows = (
        await session.execute(
            select(AgentCert.agentId, func.count())
            .where(AgentCert.status == "active")
            .group_by(AgentCert.agentId)
        )
    ).all()
    return {agent_id: count for agent_id, count in rows}


@router.get("/integrity-warnings", dependencies=[Depends(require_role("viewer"))])
async def integrity_warnings(session: AsyncSession = Depends(get_session)) -> dict:
    """Governance-integrity checks. P0: an agent at L3+ autonomy with zero active certs — the exact
    failure SimForge exists to prevent (autonomy not backed by a live cert)."""
    active_by_agent = await _active_certs_by_agent(session)
    agents = (await session.execute(select(Agent))).scalars().all()

    warnings: list[dict] = []
    for agent in agents:
        rank = _LADDER_RANK.get(agent.currentAutonomyLevel, 1)
        active = active_by_agent.get(agent.id, 0)
        if rank >= 3 and active == 0:
            warnings.append(
                {
                    "agent_id": agent.villageAgentId,
                    "warning_type": "autonomy_without_certs",
                    "detail": (
                        f"{agent.villageAgentId} is at {agent.currentAutonomyLevel} with 0 active "
                        "certs — auto-downgrade may not have fired."
                    ),
                    "autonomy_level": agent.currentAutonomyLevel,
                    "active_certs": active,
                    "severity": "high",
                }
            )
    return {"warnings": warnings, "total": len(warnings)}


@router.get("/runs-per-day", dependencies=[Depends(require_role("viewer"))])
async def runs_per_day(
    days: int = Query(default=14, ge=1, le=90), session: AsyncSession = Depends(get_session)
) -> dict:
    """A zero-filled runs/day series for the last `days` days — the throughput trend."""
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=days - 1)
    rows = (
        await session.execute(
            select(func.date(Run.startedAt), func.count())
            .where(Run.startedAt >= start)
            .group_by(func.date(Run.startedAt))
        )
    ).all()
    counts = {str(day): count for day, count in rows}
    series = [
        {
            "date": (start + timedelta(days=i)).date().isoformat(),
            "count": counts.get((start + timedelta(days=i)).date().isoformat(), 0),
        }
        for i in range(days)
    ]
    return {"days": days, "series": series}


@router.get("/agent-certs", dependencies=[Depends(require_role("viewer"))])
async def agent_certs_summary(session: AsyncSession = Depends(get_session)) -> dict:
    """Per-agent cert rollup (active/total/last-certified) for the Agents + Readiness views."""
    agents = (await session.execute(select(Agent))).scalars().all()
    name_by_id = {a.id: a.villageAgentId for a in agents}
    certs = (await session.execute(select(AgentCert))).scalars().all()

    rollup: dict[str, dict] = {
        a.villageAgentId: {"active_certs": 0, "total_certs": 0, "last_certified_at": None}
        for a in agents
    }
    for c in certs:
        vid = name_by_id.get(c.agentId)
        if vid is None:
            continue
        entry = rollup[vid]
        entry["total_certs"] += 1
        if c.status == "active":
            entry["active_certs"] += 1
        iso = c.issuedAt.isoformat() if c.issuedAt else None
        if iso and (entry["last_certified_at"] is None or iso > entry["last_certified_at"]):
            entry["last_certified_at"] = iso
    return {"items": [{"agent_village_id": k, **v} for k, v in rollup.items()]}


# --- §10.4 dashboards: coverage heatmap, dept×context, cognitive trends, cert timeline, CCB diff


@router.get("/coverage-heatmap", dependencies=[Depends(require_role("viewer"))])
async def coverage_heatmap(session: AsyncSession = Depends(get_session)) -> dict:
    """(role × tier) scenario coverage per pack (§10.4). `tier` is the persisted certification
    axis (§6.2 `stage` is a YAML-only field, not stored), so the heatmap reports role × tier."""
    from src.models.pack import Pack, Scenario

    packs = {p.id: p.packId for p in (await session.execute(select(Pack))).scalars().all()}
    scenarios = (await session.execute(select(Scenario))).scalars().all()
    cells: dict[tuple[str, str, str], int] = {}
    for s in scenarios:
        key = (packs.get(s.packId, s.packId), s.testedAgentVillageId, s.tier)
        cells[key] = cells.get(key, 0) + 1
    return {
        "axis": "tier",
        "cells": [
            {"pack": pk, "role": role, "tier": tier, "count": n, "meets_min": n >= 3}
            for (pk, role, tier), n in sorted(cells.items())
        ],
        "min_per_cell": 3,
    }


@router.get("/dept-context-matrix", dependencies=[Depends(require_role("viewer"))])
async def dept_context_matrix(session: AsyncSession = Depends(get_session)) -> dict:
    """The DeptCert (department × forge-context) half of the readiness matrix (§10.4 / D2)."""
    from src.models.cert import DeptCert
    from src.models.department import Department

    depts = {
        d.id: d.villageKey for d in (await session.execute(select(Department))).scalars().all()
    }
    certs = (await session.execute(select(DeptCert))).scalars().all()
    contexts = sorted({c.forgeContext for c in certs})
    cells = [
        {
            "department": depts.get(c.departmentId, c.departmentId),
            "forge_context": c.forgeContext,
            "tier": c.tier,
            "status": c.status,
            "covering_certs": len(c.prerequisiteAgentCertIds or []),
        }
        for c in certs
    ]
    return {"forge_contexts": contexts, "cells": cells, "total_dept_certs": len(certs)}


@router.get("/cognitive-trends/{agent_village_id}", dependencies=[Depends(require_role("viewer"))])
async def cognitive_trends(
    agent_village_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    """Per-agent cognitive-dimension time series from stored snapshots (§10.4)."""
    from src.models.cognitive_snapshot import CognitiveSnapshot

    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == agent_village_id))
    ).scalar_one_or_none()
    if agent is None:
        return {"agent": agent_village_id, "points": [], "has_trend": False}
    rows = (
        (
            await session.execute(
                select(CognitiveSnapshot)
                .where(CognitiveSnapshot.agentId == agent.id)
                .order_by(CognitiveSnapshot.date.asc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "agent": agent_village_id,
        "points": [
            {
                "date": r.date.isoformat() if r.date else None,
                "values": r.values,
                "deltas": r.deltas,
                "drift_magnitude": r.driftMagnitude,
            }
            for r in rows
        ],
        "has_trend": len({r.date for r in rows}) >= 2,
    }


@router.get("/cert-timeline", dependencies=[Depends(require_role("viewer"))])
async def cert_timeline(
    limit: int = Query(default=100, ge=1, le=500), session: AsyncSession = Depends(get_session)
) -> dict:
    """Certification lifecycle events as a timeline (issued/renewed/suspended/revoked…) — §10.4."""
    from src.models.cert import CertLifecycleEvent

    rows = (
        (
            await session.execute(
                select(CertLifecycleEvent)
                .order_by(CertLifecycleEvent.timestamp.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "events": [
            {
                "event": e.event,
                "agent_cert_id": e.agentCertId,
                "dept_cert_id": e.deptCertId,
                "actor": e.actor,
                "reason": e.reason,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in rows
        ]
    }


@router.get("/ccb-diff/{run_id}", dependencies=[Depends(require_role("viewer"))])
async def ccb_diff(run_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """CCB pre→post diff for a run — standalone artifact (§10.4), per-framework changed keys."""
    from src.models.ccb import CCB as CCBModel

    run = (await session.execute(select(Run).where(Run.runId == run_id))).scalar_one_or_none()
    if run is None:
        return {"run_id": run_id, "available": False, "reason": "run not found"}
    if not run.ccbPreId or not run.ccbPostId:
        return {"run_id": run_id, "available": False, "reason": "no CCB captured for this run"}
    pre = (
        await session.execute(select(CCBModel).where(CCBModel.id == run.ccbPreId))
    ).scalar_one_or_none()
    post = (
        await session.execute(select(CCBModel).where(CCBModel.id == run.ccbPostId))
    ).scalar_one_or_none()
    if pre is None or post is None:
        return {"run_id": run_id, "available": False, "reason": "CCB rows missing"}

    frameworks = ("game", "mate", "soul", "breath", "fot", "hfm", "arc", "echo", "drift", "ame")
    diffs: list[dict] = []
    for fw in frameworks:
        pre_v = getattr(pre, fw, None) or {}
        post_v = getattr(post, fw, None) or {}
        changed = sorted(k for k in set(pre_v) | set(post_v) if pre_v.get(k) != post_v.get(k))
        if changed:
            diffs.append(
                {
                    "framework": fw,
                    "changed_keys": changed,
                    "before": {k: pre_v.get(k) for k in changed},
                    "after": {k: post_v.get(k) for k in changed},
                }
            )
    return {
        "run_id": run_id,
        "available": True,
        "identical": len(diffs) == 0,
        "diffs": diffs,
    }

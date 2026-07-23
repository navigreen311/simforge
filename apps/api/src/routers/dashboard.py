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

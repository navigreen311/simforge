"""Dashboard aggregates router (blueprint §C.3.10)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.agent import Agent
from src.models.cert import AgentCert
from src.models.gap import SoftwareGap, VillageOSGap
from src.models.run import Run

router = APIRouter()


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
        "open_software_gaps": await _count(SoftwareGap, SoftwareGap.status == "open"),
        "open_village_os_gaps": await _count(VillageOSGap, VillageOSGap.status == "open"),
    }

"""PDP router — the authorization decision endpoint PEPs call (blueprint §F.6; ADR-0024)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.agent import Agent
from src.models.cert import AgentCert
from src.schemas.pdp import (
    AuthDecisionOut,
    AuthRequestBody,
    EffectivePermission,
    EffectivePermissionsOut,
)
from src.services.governance.pdp import AuthRequest, pdp
from src.telemetry.metrics import PDP_DECISION_LATENCY, PDP_DECISIONS_TOTAL

router = APIRouter()


@router.post(
    "/decide", response_model=AuthDecisionOut, dependencies=[Depends(require_role("viewer"))]
)
async def decide(
    body: AuthRequestBody, session: AsyncSession = Depends(get_session)
) -> AuthDecisionOut:
    """Authorize (or not) an agent action. Read-only; PEPs cache the result for `ttl_seconds`."""
    started = time.perf_counter()
    req = AuthRequest(
        subject_agent_id=body.subject_agent_id,
        action=body.action,
        resource=body.resource,
        context=body.context,
    )
    decision = await pdp.decide(session, req)
    PDP_DECISION_LATENCY.labels(decision=decision.decision).observe(time.perf_counter() - started)
    PDP_DECISIONS_TOTAL.labels(decision=decision.decision, reason_code=decision.reason_code).inc()
    return AuthDecisionOut(**decision.as_dict())


@router.get(
    "/agent/{agent_id}/effective",
    response_model=EffectivePermissionsOut,
    dependencies=[Depends(require_role("viewer"))],
)
async def effective_permissions(
    agent_id: str, session: AsyncSession = Depends(get_session)
) -> EffectivePermissionsOut:
    """The agent's effective permissions — a PDP decision per cert it holds (dashboards/audit)."""
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == agent_id))
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    certs = (
        (await session.execute(select(AgentCert).where(AgentCert.agentId == agent.id)))
        .scalars()
        .all()
    )
    perms: list[EffectivePermission] = []
    for cert in certs:
        d = await pdp.decide(session, AuthRequest(subject_agent_id=agent_id, action=cert.forgeCap))
        perms.append(
            EffectivePermission(
                action=cert.forgeCap,
                tier=cert.tier,
                cert_status=cert.status,
                decision=d.decision,
                reason_code=d.reason_code,
            )
        )
    return EffectivePermissionsOut(
        subject_agent_id=agent_id, autonomy_level=agent.currentAutonomyLevel, permissions=perms
    )

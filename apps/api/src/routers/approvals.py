"""Approvals router — the governance Approval Workflow Engine (§11.5)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.approval import ApprovalDecision, ApprovalRequest
from src.services.governance.approval import (
    ApprovalError,
    cast_vote,
    create_request,
    expire_stale_requests,
    withdraw_request,
)

router = APIRouter()


class CreateApprovalBody(BaseModel):
    kind: str
    subject: dict = {}
    summary: str = ""
    quorum_rule: str = "single"
    required_approvers: list[str] = []
    created_by: str = "ivan"
    ttl_hours: int | None = 48


class VoteBody(BaseModel):
    approver: str
    decision: str  # approve | reject | abstain
    reason: str = ""


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approver: str
    decision: str
    reason: str
    timestamp: datetime


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    subject: dict
    summary: str
    quorumRule: str
    requiredApprovers: list[str]
    status: str
    createdBy: str
    createdAt: datetime
    expiresAt: datetime | None
    resolvedAt: datetime | None
    resolution: str | None


async def _journal(session: AsyncSession, request_id: str) -> list[DecisionOut]:
    rows = (
        (
            await session.execute(
                select(ApprovalDecision)
                .where(ApprovalDecision.requestId == request_id)
                .order_by(ApprovalDecision.timestamp)
            )
        )
        .scalars()
        .all()
    )
    return [DecisionOut.model_validate(r) for r in rows]


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def list_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(ApprovalRequest).order_by(ApprovalRequest.createdAt.desc())
    if status_filter:
        stmt = stmt.where(ApprovalRequest.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return {"requests": [RequestOut.model_validate(r).model_dump(mode="json") for r in rows]}


@router.get("/{request_id}", dependencies=[Depends(require_role("viewer"))])
async def get_request(request_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    req = (
        await session.execute(select(ApprovalRequest).where(ApprovalRequest.id == request_id))
    ).scalar_one_or_none()
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return {
        "request": RequestOut.model_validate(req).model_dump(mode="json"),
        "journal": [d.model_dump(mode="json") for d in await _journal(session, request_id)],
    }


@router.post("/", dependencies=[Depends(require_role("compliance_analyst"))])
async def create(body: CreateApprovalBody, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        req = await create_request(
            session,
            kind=body.kind,
            subject=body.subject,
            summary=body.summary,
            quorum_rule=body.quorum_rule,
            required_approvers=body.required_approvers,
            created_by=body.created_by,
            ttl_hours=body.ttl_hours,
        )
    except ApprovalError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RequestOut.model_validate(req).model_dump(mode="json")


@router.post("/{request_id}/vote", dependencies=[Depends(require_role("compliance_analyst"))])
async def vote(
    request_id: str, body: VoteBody, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        req = await cast_vote(
            session,
            request_id,
            approver=body.approver,
            decision=body.decision,
            reason=body.reason,
        )
    except ApprovalError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "request": RequestOut.model_validate(req).model_dump(mode="json"),
        "journal": [d.model_dump(mode="json") for d in await _journal(session, request_id)],
    }


@router.post("/{request_id}/withdraw", dependencies=[Depends(require_role("compliance_analyst"))])
async def withdraw(
    request_id: str,
    actor: str = Query(default="ivan"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        req = await withdraw_request(session, request_id, actor)
    except ApprovalError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RequestOut.model_validate(req).model_dump(mode="json")


@router.post("/expire-stale", dependencies=[Depends(require_role("admin"))])
async def expire_stale(session: AsyncSession = Depends(get_session)) -> dict:
    """Auto-escalation sweep: mark pending requests past their TTL as expired."""
    expired = await expire_stale_requests(session)
    return {"expired": expired, "count": len(expired)}

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


# --- Waivers + Appeals (§11.5) ---

waivers_router = APIRouter()
appeals_router = APIRouter()


class GrantWaiverBody(BaseModel):
    subject: str
    scope: str
    reason: str = ""
    ttl_hours: int = 24
    compensating_controls: list[str] = []
    granted_by: str = "admin"


class FileAppealBody(BaseModel):
    target_id: str
    appellant: str
    grounds: str = ""
    target_type: str = "cert_decision"


class AssignReviewerBody(BaseModel):
    reviewer: str


class ResolveAppealBody(BaseModel):
    decision: str  # upheld | overturned
    note: str = ""
    escalate_to_founder: bool = False


def _waiver_out(w) -> dict:  # noqa: ANN001
    return {
        "id": w.id,
        "subject": w.subject,
        "scope": w.scope,
        "reason": w.reason,
        "compensating_controls": list(w.compensatingControls or []),
        "status": w.status,
        "granted_by": w.grantedBy,
        "expires_at": w.expiresAt.isoformat() if w.expiresAt else None,
    }


def _appeal_out(a) -> dict:  # noqa: ANN001
    return {
        "id": a.id,
        "target_type": a.targetType,
        "target_id": a.targetId,
        "appellant": a.appellant,
        "grounds": a.grounds,
        "original_approver": a.originalApprover,
        "status": a.status,
        "second_reviewer": a.secondReviewer,
        "reviewer_decision": a.reviewerDecision,
        "resolution_note": a.resolutionNote,
        "escalated_to_founder": a.escalatedToFounder,
    }


@waivers_router.get("/", dependencies=[Depends(require_role("viewer"))])
async def list_waivers(session: AsyncSession = Depends(get_session)) -> dict:
    from src.services.governance.waiver import active_waivers

    return {"waivers": [_waiver_out(w) for w in await active_waivers(session)]}


@waivers_router.post("/", dependencies=[Depends(require_role("compliance_analyst"))])
async def grant_waiver_endpoint(
    body: GrantWaiverBody, session: AsyncSession = Depends(get_session)
) -> dict:
    from src.services.governance.waiver import WaiverError, grant_waiver

    try:
        w = await grant_waiver(
            session,
            subject=body.subject,
            scope=body.scope,
            reason=body.reason,
            ttl_hours=body.ttl_hours,
            compensating_controls=body.compensating_controls,
            granted_by=body.granted_by,
        )
    except WaiverError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _waiver_out(w)


@waivers_router.post("/{waiver_id}/revoke", dependencies=[Depends(require_role("admin"))])
async def revoke_waiver_endpoint(
    waiver_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    from src.services.governance.waiver import WaiverError, revoke_waiver

    try:
        w = await revoke_waiver(session, waiver_id, "admin")
    except WaiverError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _waiver_out(w)


@appeals_router.get("/", dependencies=[Depends(require_role("viewer"))])
async def list_appeals(session: AsyncSession = Depends(get_session)) -> dict:
    from src.models.waiver import Appeal

    rows = (await session.execute(select(Appeal).order_by(Appeal.createdAt.desc()))).scalars().all()
    return {"appeals": [_appeal_out(a) for a in rows]}


@appeals_router.post("/", dependencies=[Depends(require_role("viewer"))])
async def file_appeal_endpoint(
    body: FileAppealBody, session: AsyncSession = Depends(get_session)
) -> dict:
    from src.services.governance.waiver import WaiverError, file_appeal

    try:
        a = await file_appeal(
            session,
            target_id=body.target_id,
            appellant=body.appellant,
            grounds=body.grounds,
            target_type=body.target_type,
        )
    except WaiverError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _appeal_out(a)


@appeals_router.post(
    "/{appeal_id}/assign", dependencies=[Depends(require_role("compliance_analyst"))]
)
async def assign_reviewer_endpoint(
    appeal_id: str, body: AssignReviewerBody, session: AsyncSession = Depends(get_session)
) -> dict:
    from src.services.governance.waiver import WaiverError, assign_reviewer

    try:
        a = await assign_reviewer(session, appeal_id, body.reviewer)
    except WaiverError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _appeal_out(a)


@appeals_router.post("/{appeal_id}/resolve", dependencies=[Depends(require_role("admin"))])
async def resolve_appeal_endpoint(
    appeal_id: str, body: ResolveAppealBody, session: AsyncSession = Depends(get_session)
) -> dict:
    from src.services.governance.waiver import WaiverError, resolve_appeal

    try:
        a = await resolve_appeal(
            session,
            appeal_id,
            decision=body.decision,
            note=body.note,
            escalate_to_founder=body.escalate_to_founder,
        )
    except WaiverError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _appeal_out(a)

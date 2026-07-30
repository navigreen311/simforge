"""Approval Workflow Engine (§11.5).

Governed decisions route through here: create a request with a quorum rule + TTL, approvers cast
signed votes (the append-only decision journal), and the request resolves by quorum or expires.

Quorum rules:
  - single       → one approve resolves it (one reject rejects it).
  - two_of_three → ≥2 approvals resolve; ≥2 rejections reject.
  - unanimous    → every required approver must approve; any reject rejects immediately.

Time-bound: a request past its TTL is `expired` (auto-escalation is surfaced by listing expired
pending requests; the sweep marks them). Every vote is recorded with the approver identity + a
signed reason (decision journal), never mutated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.approval import (
    APPROVAL_KINDS,
    QUORUM_RULES,
    ApprovalDecision,
    ApprovalRequest,
)
from src.utils.time import utcnow


class ApprovalError(Exception):
    """Invalid workflow operation (bad kind/quorum, double vote, resolved request)."""


@dataclass
class QuorumOutcome:
    resolved: bool
    resolution: str | None  # approved | rejected | None


def _tally(
    decisions: list[ApprovalDecision], quorum_rule: str, required_approvers: list[str]
) -> QuorumOutcome:
    approvals = sum(1 for d in decisions if d.decision == "approve")
    rejections = sum(1 for d in decisions if d.decision == "reject")

    if quorum_rule == "single":
        if rejections >= 1:
            return QuorumOutcome(True, "rejected")
        if approvals >= 1:
            return QuorumOutcome(True, "approved")
    elif quorum_rule == "two_of_three":
        if rejections >= 2:
            return QuorumOutcome(True, "rejected")
        if approvals >= 2:
            return QuorumOutcome(True, "approved")
    elif quorum_rule == "unanimous":
        if rejections >= 1:
            return QuorumOutcome(True, "rejected")
        needed = set(required_approvers)
        approved_by = {d.approver for d in decisions if d.decision == "approve"}
        if needed and needed <= approved_by:
            return QuorumOutcome(True, "approved")
    return QuorumOutcome(False, None)


async def create_request(
    session: AsyncSession,
    *,
    kind: str,
    subject: dict,
    summary: str = "",
    quorum_rule: str = "single",
    required_approvers: list[str] | None = None,
    created_by: str = "system",
    ttl_hours: int | None = 48,
) -> ApprovalRequest:
    if kind not in APPROVAL_KINDS:
        raise ApprovalError(f"kind must be one of {APPROVAL_KINDS}")
    if quorum_rule not in QUORUM_RULES:
        raise ApprovalError(f"quorum_rule must be one of {QUORUM_RULES}")
    approvers = required_approvers or []
    if quorum_rule == "unanimous" and not approvers:
        raise ApprovalError("unanimous quorum requires a non-empty required_approvers list")
    now = utcnow()
    req = ApprovalRequest(
        kind=kind,
        subject=subject,
        summary=summary,
        quorumRule=quorum_rule,
        requiredApprovers=approvers,
        status="pending",
        createdBy=created_by,
        createdAt=now,
        expiresAt=(now + timedelta(hours=ttl_hours)) if ttl_hours else None,
    )
    session.add(req)
    await session.commit()
    await session.refresh(req)
    return req


async def _decisions(session: AsyncSession, request_id: str) -> list[ApprovalDecision]:
    return list(
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


async def cast_vote(
    session: AsyncSession,
    request_id: str,
    *,
    approver: str,
    decision: str,
    reason: str = "",
) -> ApprovalRequest:
    """Record a signed vote and resolve the request if quorum is now met."""
    if decision not in ("approve", "reject", "abstain"):
        raise ApprovalError("decision must be approve | reject | abstain")
    req = (
        await session.execute(select(ApprovalRequest).where(ApprovalRequest.id == request_id))
    ).scalar_one_or_none()
    if req is None:
        raise ApprovalError(f"Request not found: {request_id}")
    if req.status != "pending":
        raise ApprovalError(f"Request already {req.status}")
    now = utcnow()
    if req.expiresAt is not None and now > req.expiresAt:
        req.status = "expired"
        req.resolution = "expired"
        req.resolvedAt = now
        await session.commit()
        raise ApprovalError("Request has expired")

    existing = await _decisions(session, request_id)
    if any(d.approver == approver for d in existing):
        raise ApprovalError(f"{approver} has already voted on this request")

    session.add(
        ApprovalDecision(
            requestId=request_id, approver=approver, decision=decision, reason=reason, timestamp=now
        )
    )
    await session.flush()

    outcome = _tally(
        [
            *existing,
            ApprovalDecision(
                requestId=request_id, approver=approver, decision=decision, reason=reason
            ),
        ],
        req.quorumRule,
        list(req.requiredApprovers or []),
    )
    if outcome.resolved:
        req.status = outcome.resolution or "pending"
        req.resolution = outcome.resolution
        req.resolvedAt = now
    await session.commit()
    await session.refresh(req)
    return req


async def withdraw_request(session: AsyncSession, request_id: str, actor: str) -> ApprovalRequest:
    req = (
        await session.execute(select(ApprovalRequest).where(ApprovalRequest.id == request_id))
    ).scalar_one_or_none()
    if req is None:
        raise ApprovalError(f"Request not found: {request_id}")
    if req.status != "pending":
        raise ApprovalError(f"Request already {req.status}")
    now = utcnow()
    req.status = "withdrawn"
    req.resolution = "withdrawn"
    req.resolvedAt = now
    session.add(
        ApprovalDecision(
            requestId=request_id,
            approver=actor,
            decision="abstain",
            reason="withdrawn",
            timestamp=now,
        )
    )
    await session.commit()
    await session.refresh(req)
    return req


async def expire_stale_requests(session: AsyncSession) -> list[str]:
    """Mark pending requests past their TTL as expired (auto-escalation sweep); returns ids."""
    now = utcnow()
    stale = (
        (
            await session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.status == "pending",
                    ApprovalRequest.expiresAt.is_not(None),
                    ApprovalRequest.expiresAt < now,
                )
            )
        )
        .scalars()
        .all()
    )
    for req in stale:
        req.status = "expired"
        req.resolution = "expired"
        req.resolvedAt = now
    if stale:
        await session.commit()
    return [r.id for r in stale]

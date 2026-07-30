"""Waiver + Appeal service (§11.5).

Waivers are temporary, expiring exception grants (with compensating controls). Appeals challenge a
cert decision within a 7-day window and route to a second reviewer who must differ from the original
approver, with Ivan as the final escalation. Both keep a full audit trail.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cert import CertLifecycleEvent
from src.models.waiver import Appeal, Waiver
from src.utils.time import utcnow

APPEAL_WINDOW_DAYS = 7


class WaiverError(Exception):
    """Invalid waiver/appeal operation."""


# ---- Waivers ----


async def grant_waiver(
    session: AsyncSession,
    *,
    subject: str,
    scope: str,
    reason: str,
    ttl_hours: int,
    compensating_controls: list[str] | None = None,
    granted_by: str = "admin",
) -> Waiver:
    if ttl_hours <= 0:
        raise WaiverError("A waiver must have a positive TTL")
    now = utcnow()
    w = Waiver(
        subject=subject,
        scope=scope,
        reason=reason,
        compensatingControls=compensating_controls or [],
        status="active",
        grantedBy=granted_by,
        grantedAt=now,
        expiresAt=now + timedelta(hours=ttl_hours),
    )
    session.add(w)
    await session.commit()
    await session.refresh(w)
    return w


async def revoke_waiver(session: AsyncSession, waiver_id: str, actor: str) -> Waiver:
    w = (await session.execute(select(Waiver).where(Waiver.id == waiver_id))).scalar_one_or_none()
    if w is None:
        raise WaiverError(f"Waiver not found: {waiver_id}")
    if w.status != "active":
        raise WaiverError(f"Waiver already {w.status}")
    w.status = "revoked"
    w.revokedAt = utcnow()
    await session.commit()
    await session.refresh(w)
    return w


async def active_waivers(session: AsyncSession, subject: str | None = None) -> list[Waiver]:
    now = utcnow()
    stmt = select(Waiver).where(Waiver.status == "active", Waiver.expiresAt > now)
    if subject:
        stmt = stmt.where(Waiver.subject == subject)
    return list((await session.execute(stmt)).scalars().all())


async def expire_waivers(session: AsyncSession) -> list[str]:
    """Mark active waivers past their TTL as expired (cadence sweep). Returns their ids."""
    now = utcnow()
    stale = (
        (
            await session.execute(
                select(Waiver).where(Waiver.status == "active", Waiver.expiresAt <= now)
            )
        )
        .scalars()
        .all()
    )
    for w in stale:
        w.status = "expired"
    if stale:
        await session.commit()
    return [w.id for w in stale]


# ---- Appeals ----


async def file_appeal(
    session: AsyncSession,
    *,
    target_id: str,
    appellant: str,
    grounds: str,
    target_type: str = "cert_decision",
) -> Appeal:
    """File an appeal against a cert decision. The most-recent lifecycle event dates the decision;
    appeals must be filed within APPEAL_WINDOW_DAYS of it."""
    now = utcnow()
    original_approver = None
    if target_type == "cert_decision":
        ev = (
            (
                await session.execute(
                    select(CertLifecycleEvent)
                    .where(CertLifecycleEvent.agentCertId == target_id)
                    .order_by(CertLifecycleEvent.timestamp.desc())
                )
            )
            .scalars()
            .first()
        )
        if ev is None:
            raise WaiverError(f"No cert decision found to appeal: {target_id}")
        if now - ev.timestamp > timedelta(days=APPEAL_WINDOW_DAYS):
            raise WaiverError(
                f"Appeal window closed: the decision is older than {APPEAL_WINDOW_DAYS} days"
            )
        original_approver = ev.actor

    appeal = Appeal(
        targetType=target_type,
        targetId=target_id,
        appellant=appellant,
        grounds=grounds,
        originalApprover=original_approver,
        status="open",
    )
    session.add(appeal)
    await session.commit()
    await session.refresh(appeal)
    return appeal


async def assign_reviewer(session: AsyncSession, appeal_id: str, reviewer: str) -> Appeal:
    """Assign a second reviewer — must differ from the original approver (§11.5)."""
    a = (await session.execute(select(Appeal).where(Appeal.id == appeal_id))).scalar_one_or_none()
    if a is None:
        raise WaiverError(f"Appeal not found: {appeal_id}")
    if a.status not in ("open", "under_review"):
        raise WaiverError(f"Appeal already {a.status}")
    if a.originalApprover and reviewer == a.originalApprover:
        raise WaiverError("The second reviewer must differ from the original approver")
    a.secondReviewer = reviewer
    a.status = "under_review"
    await session.commit()
    await session.refresh(a)
    return a


async def resolve_appeal(
    session: AsyncSession,
    appeal_id: str,
    *,
    decision: str,
    note: str = "",
    escalate_to_founder: bool = False,
) -> Appeal:
    """Resolve an appeal: upheld (original decision stands) or overturned. `escalate_to_founder`
    records the Ivan final-escalation path."""
    if decision not in ("upheld", "overturned"):
        raise WaiverError("decision must be 'upheld' or 'overturned'")
    a = (await session.execute(select(Appeal).where(Appeal.id == appeal_id))).scalar_one_or_none()
    if a is None:
        raise WaiverError(f"Appeal not found: {appeal_id}")
    if a.status not in ("open", "under_review"):
        raise WaiverError(f"Appeal already {a.status}")
    if a.secondReviewer is None and not escalate_to_founder:
        raise WaiverError("Assign a second reviewer (or escalate to founder) before resolving")
    a.status = "upheld" if decision == "upheld" else "overturned"
    a.reviewerDecision = decision
    a.resolutionNote = note
    a.escalatedToFounder = escalate_to_founder
    a.resolvedAt = utcnow()
    await session.commit()
    await session.refresh(a)
    return a

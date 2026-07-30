"""Constitutional amendment workflow (blueprint §F.5).

propose → cooling period → ratify (Ivan + quorum) | withdraw | veto. On ratification a new
Constitution version supersedes the base, and affected certs auto-suspend pending re-cert.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from src.models.cert import AgentCert, CertLifecycleEvent, CertSnapshot
from src.models.governance import Constitution, ConstitutionalAmendment
from src.services.governance.constitution import (
    AMENDMENT_PROCESS_ARTICLE,
    get_current_constitution,
)
from src.utils.time import utcnow

COOLING_DAYS_DEFAULT = 7
# Meta-amendments (amending the amendment process itself) need a longer cooling + unanimous quorum.
META_COOLING_DAYS = 14


class AmendmentError(Exception):
    """Raised on invalid amendment transitions."""


def _bump_patch(version: str) -> str:
    v = version.lstrip("v").split(".")
    while len(v) < 3:
        v.append("0")
    v[2] = str(int(v[2]) + 1)
    return "v" + ".".join(v[:3])


async def _count_affected_certs(session: AsyncSession, constitution_version: str) -> int:
    certs = (
        (await session.execute(select(AgentCert).where(AgentCert.status == "active")))
        .scalars()
        .all()
    )
    count = 0
    for c in certs:
        snap = (
            await session.execute(select(CertSnapshot).where(CertSnapshot.id == c.certSnapshotId))
        ).scalar_one_or_none()
        if snap and snap.pinnedVersions.get("constitution_version") == constitution_version:
            count += 1
    return count


async def propose_amendment(
    session: AsyncSession,
    proposer: str,
    diff_yaml: str,
    cooling_days: int = COOLING_DAYS_DEFAULT,
    *,
    target_article: str | None = None,
    required_approvers: list[str] | None = None,
    quorum_rule: str | None = None,
) -> ConstitutionalAmendment:
    """Propose an amendment. A META-amendment (target_article == the amendment-process article, or
    an explicit unanimous request) forces a 14-day cooling + unanimous founder+witness quorum
    (§11.6). When approvers are declared (always for meta), ratification is gated by a §11.5
    ApprovalRequest; the simple no-approver path stays cooling-only (back-compat)."""
    base = await get_current_constitution(session)
    if base is None:
        raise AmendmentError("No ratified constitution to amend")

    is_meta = target_article == AMENDMENT_PROCESS_ARTICLE
    approvers = list(required_approvers or [])
    if is_meta:
        cooling_days = max(cooling_days, META_COOLING_DAYS)
        quorum_rule = "unanimous"
        if len(approvers) < 2:
            raise AmendmentError(
                "A meta-amendment (amending the amendment process) requires ≥2 named approvers "
                "(founder + witness) under unanimous quorum (§11.6)."
            )
    quorum_rule = quorum_rule or "single"

    now = utcnow()
    impact: dict = {
        "affected_certs": await _count_affected_certs(session, base.version),
        "is_meta": is_meta,
        "target_article": target_article,
        "quorum_rule": quorum_rule if approvers else None,
    }

    # If approvers are declared, gate ratification on a §11.5 approval request (quorum + journal).
    if approvers:
        from src.services.governance.approval import create_request

        req = await create_request(
            session,
            kind="constitutional_amendment",
            subject={"target_article": target_article, "proposer": proposer, "meta": is_meta},
            summary=f"{'META ' if is_meta else ''}amendment to {target_article or 'constitution'}",
            quorum_rule=quorum_rule,
            required_approvers=approvers,
            created_by=proposer,
            ttl_hours=cooling_days * 24 + 24,  # let approvals accrue through the cooling window
        )
        impact["approval_request_id"] = req.id

    amendment = ConstitutionalAmendment(
        amendmentId=f"amend:{ULID()}",
        baseConstitutionId=base.id,
        proposedAt=now,
        proposedBy=proposer,
        coolingPeriodEndsAt=now + timedelta(days=cooling_days),
        diffYaml=diff_yaml,
        impactAnalysis=impact,
        status="in_cooling",
    )
    session.add(amendment)
    await session.commit()
    await session.refresh(amendment)
    return amendment


async def _get_amendment(session: AsyncSession, amendment_id: str) -> ConstitutionalAmendment:
    a = (
        await session.execute(
            select(ConstitutionalAmendment).where(
                ConstitutionalAmendment.amendmentId == amendment_id
            )
        )
    ).scalar_one_or_none()
    if a is None:
        raise AmendmentError(f"Amendment not found: {amendment_id}")
    return a


async def withdraw_amendment(
    session: AsyncSession, amendment_id: str, actor: str
) -> ConstitutionalAmendment:
    a = await _get_amendment(session, amendment_id)
    if a.status not in ("proposed", "in_cooling"):
        raise AmendmentError(f"Cannot withdraw amendment in status {a.status}")
    a.status = "withdrawn"
    await session.commit()
    return a


async def veto_amendment(
    session: AsyncSession, amendment_id: str, actor: str
) -> ConstitutionalAmendment:
    a = await _get_amendment(session, amendment_id)
    if a.status in ("ratified", "withdrawn"):
        raise AmendmentError(f"Cannot veto amendment in status {a.status}")
    a.status = "vetoed"
    await session.commit()
    return a


async def ratify_amendment(session: AsyncSession, amendment_id: str, ratified_by: str) -> dict:
    a = await _get_amendment(session, amendment_id)
    if a.status != "in_cooling":
        raise AmendmentError(f"Cannot ratify amendment in status {a.status}")
    if a.coolingPeriodEndsAt > utcnow():
        raise AmendmentError("Cooling period has not ended")

    # Quorum gate (§11.6): if the proposal declared approvers, its linked approval request must be
    # resolved 'approved' before ratification. No linked request → cooling-only (back-compat).
    approval_request_id = (a.impactAnalysis or {}).get("approval_request_id")
    if approval_request_id:
        from src.models.approval import ApprovalRequest

        req = (
            await session.execute(
                select(ApprovalRequest).where(ApprovalRequest.id == approval_request_id)
            )
        ).scalar_one_or_none()
        if req is None or req.status != "approved":
            raise AmendmentError(
                f"Quorum not met: approval request is "
                f"'{req.status if req else 'missing'}', not 'approved' (§11.6)."
            )

    base = (
        await session.execute(select(Constitution).where(Constitution.id == a.baseConstitutionId))
    ).scalar_one()
    new_version = _bump_patch(base.version)
    now = utcnow()

    new_yaml = base.yamlContent + f"\n# amended by {amendment_id} at {now.isoformat()}\n"
    new_const = Constitution(
        version=new_version,
        ratifiedAt=now,
        ratifiedBy=ratified_by,
        yamlContent=new_yaml,
        contentHash=hashlib.sha256(new_yaml.encode()).hexdigest(),
    )
    session.add(new_const)
    base.supersededByVersion = new_version
    base.supersededAt = now
    a.status = "ratified"
    a.ratifiedAt = now
    a.ratifiedBy = ratified_by

    # Affected certs auto-suspend pending re-certification.
    suspended = 0
    certs = (
        (await session.execute(select(AgentCert).where(AgentCert.status == "active")))
        .scalars()
        .all()
    )
    suspended_certs: list[AgentCert] = []
    for c in certs:
        snap = (
            await session.execute(select(CertSnapshot).where(CertSnapshot.id == c.certSnapshotId))
        ).scalar_one_or_none()
        if snap and snap.pinnedVersions.get("constitution_version") == base.version:
            c.status = "suspended"
            session.add(
                CertLifecycleEvent(
                    agentCertId=c.id,
                    event="suspended",
                    timestamp=now,
                    actor=ratified_by,
                    reason=f"constitution amended to {new_version}",
                )
            )
            suspended += 1
            suspended_certs.append(c)

    await session.commit()

    # Real-time PEP cache invalidation for each amendment-suspended cert (best-effort; §F.4).
    if suspended_certs:
        from src.models.agent import Agent
        from src.services.governance.revocation import publish_cert_event

        for c in suspended_certs:
            agent = (
                await session.execute(select(Agent).where(Agent.id == c.agentId))
            ).scalar_one_or_none()
            if agent is not None:
                await publish_cert_event(agent.villageAgentId, c.forgeCap, "suspended")

    return {
        "amendment_id": amendment_id,
        "new_version": new_version,
        "superseded": base.version,
        "certs_suspended": suspended,
    }

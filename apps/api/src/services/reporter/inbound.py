"""Linear INBOUND webhook handling (§C.11).

The outbound path files a gap as a Linear issue and stores its `linearId`. This closes the loop:
when that issue changes state in Linear (someone marks it Done / Canceled), Linear POSTs a webhook
and we reflect the new state back onto the SoftwareGap / VillageOSGap. Signature verification uses
the Linear-Signature HMAC when a secret is configured; in dev (no secret) events are accepted with
a warning so the loop is testable without provisioning Linear.
"""

from __future__ import annotations

import hashlib
import hmac

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.gap import SoftwareGap, VillageOSGap
from src.telemetry.logging import get_logger

log = get_logger("linear_inbound")

# Linear workflow-state `type` → our gap status. A completed issue means the gap is fixed.
_STATE_TO_STATUS = {
    "completed": "resolved",
    "canceled": "wontfix",
    "started": "in_progress",
    "unstarted": "open",
    "backlog": "open",
    "triage": "open",
}


def verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """True if the request is authentic. With no configured secret (dev), accept-with-warning."""
    secret = settings.linear_webhook_secret or ""
    if not secret:
        log.warning("linear_webhook_unverified", reason="no LINEAR_WEBHOOK_SECRET set")
        return True
    if not signature_header:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


async def apply_linear_event(session: AsyncSession, payload: dict) -> dict:
    """Reflect a Linear Issue state change onto the linked gap. Idempotent; safe on unknowns."""
    if payload.get("type") != "Issue":
        return {"handled": False, "reason": f"ignored type {payload.get('type')!r}"}
    data = payload.get("data") or {}
    issue_id = data.get("id")
    if not issue_id:
        return {"handled": False, "reason": "no issue id in payload"}

    state = (data.get("state") or {}).get("type")
    new_status = _STATE_TO_STATUS.get(state)
    if new_status is None:
        return {"handled": False, "reason": f"unmapped state {state!r}", "issue_id": issue_id}

    # A gap links to exactly one Linear issue; check both gap tables.
    gap: SoftwareGap | VillageOSGap | None = (
        await session.execute(select(SoftwareGap).where(SoftwareGap.linearId == issue_id))
    ).scalar_one_or_none()
    kind = "software"
    if gap is None:
        gap = (
            await session.execute(select(VillageOSGap).where(VillageOSGap.linearId == issue_id))
        ).scalar_one_or_none()
        kind = "village_os"
    if gap is None:
        return {"handled": False, "reason": "no gap linked to issue", "issue_id": issue_id}

    old_status = gap.status
    if old_status == new_status:
        return {
            "handled": True,
            "changed": False,
            "kind": kind,
            "ticket": gap.ticketId,
            "status": new_status,
        }
    gap.status = new_status
    await session.commit()
    log.info(
        "linear_gap_status_synced",
        kind=kind,
        ticket=gap.ticketId,
        old=old_status,
        new=new_status,
        issue_id=issue_id,
    )
    return {
        "handled": True,
        "changed": True,
        "kind": kind,
        "ticket": gap.ticketId,
        "old_status": old_status,
        "new_status": new_status,
    }

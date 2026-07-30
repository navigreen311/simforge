"""Human Operating Model SLA engine + queues + shift handoff (§11.8).

Reads live entities into the queue-ownership matrix and computes each open item's SLA status
(within / at_risk / breached) from its age. Provides role-scoped triage inboxes, a shift-handoff
summary, and alert-fatigue-aware aggregation (queue-level counts, not per-item alerts).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.approval import ApprovalRequest
from src.models.gap import SoftwareGap, VillageOSGap
from src.models.training import TrainingProposal
from src.models.waiver import Appeal
from src.services.ops.registry import QUEUES, QUEUES_BY_NAME, ROLES, OpsQueue
from src.utils.time import utcnow

_AT_RISK_FRACTION = 0.75  # ≥75% of the SLA elapsed → at risk


def _age_hours(created: datetime | None, now: datetime) -> float:
    if created is None:
        return 0.0
    return max(0.0, (now - created).total_seconds() / 3600.0)


def _sla_status(age_hours: float, sla_hours: float) -> str:
    if age_hours >= sla_hours:
        return "breached"
    if age_hours >= sla_hours * _AT_RISK_FRACTION:
        return "at_risk"
    return "within"


async def _queue_items(session: AsyncSession, queue: OpsQueue, now: datetime) -> list[dict]:
    """The open items feeding a queue, each with age + SLA status."""
    items: list[dict] = []

    def _add(item_id: str, label: str, created: datetime | None) -> None:
        age = _age_hours(created, now)
        items.append(
            {
                "id": item_id,
                "label": label,
                "age_hours": round(age, 2),
                "sla_status": _sla_status(age, queue.sla_hours),
            }
        )

    if queue.name.startswith("gaps_"):
        sev = queue.name.split("_")[1].upper()  # P0/P1/P2
        for sg in (
            (
                await session.execute(
                    select(SoftwareGap).where(
                        SoftwareGap.severity == sev, SoftwareGap.status == "open"
                    )
                )
            )
            .scalars()
            .all()
        ):
            _add(sg.id, f"[SW] {sg.summary[:80]}", sg.createdAt)
        for vg in (
            (
                await session.execute(
                    select(VillageOSGap).where(
                        VillageOSGap.severity == sev, VillageOSGap.status == "open"
                    )
                )
            )
            .scalars()
            .all()
        ):
            _add(vg.id, f"[VOS] {vg.summary[:80]}", vg.createdAt)
    elif queue.name == "cert_reviews":
        for r in (
            (
                await session.execute(
                    select(ApprovalRequest).where(
                        ApprovalRequest.status == "pending",
                        ApprovalRequest.kind.in_(("cert_issuance", "cert_revocation")),
                    )
                )
            )
            .scalars()
            .all()
        ):
            _add(r.id, r.summary or r.kind, r.createdAt)
    elif queue.name == "appeal_cases":
        for a in (
            (
                await session.execute(
                    select(Appeal).where(Appeal.status.in_(("open", "under_review")))
                )
            )
            .scalars()
            .all()
        ):
            _add(a.id, f"appeal by {a.appellant}", a.createdAt)
    elif queue.name == "regression_alerts":
        for p in (
            (
                await session.execute(
                    select(TrainingProposal).where(TrainingProposal.status == "proposed")
                )
            )
            .scalars()
            .all()
        ):
            _add(p.id, f"proposal {p.currentPromptVersion}→{p.proposedPromptVersion}", p.createdAt)
    return items


async def _queue_summary(session: AsyncSession, queue: OpsQueue, now: datetime) -> dict:
    items = await _queue_items(session, queue, now)
    breached = sum(1 for i in items if i["sla_status"] == "breached")
    at_risk = sum(1 for i in items if i["sla_status"] == "at_risk")
    return {
        "name": queue.name,
        "description": queue.description,
        "owner": queue.owner,
        "backup": queue.backup,
        "role": queue.role,
        "sla_hours": queue.sla_hours,
        "open": len(items),
        "breached": breached,
        "at_risk": at_risk,
        "items": items,
    }


async def ops_report(session: AsyncSession, *, now: datetime | None = None) -> dict:
    """Full ops board: every queue with SLA status + a breach roll-up (§11.8)."""
    now = now or utcnow()
    queues = [await _queue_summary(session, q, now) for q in QUEUES]
    total_breached = sum(q["breached"] for q in queues)
    return {
        "queues": queues,
        "total_open": sum(q["open"] for q in queues),
        "total_breached": total_breached,
        "total_at_risk": sum(q["at_risk"] for q in queues),
        "health": "breached" if total_breached else "ok",
    }


async def role_inbox(session: AsyncSession, role: str, *, now: datetime | None = None) -> dict:
    """A role's triage inbox — only the queues that role owns (§11.8)."""
    now = now or utcnow()
    queues = [await _queue_summary(session, q, now) for q in QUEUES if q.role == role]
    return {
        "role": role,
        "queues": queues,
        "open": sum(q["open"] for q in queues),
        "breached": sum(q["breached"] for q in queues),
    }


async def handoff_report(session: AsyncSession, *, now: datetime | None = None) -> dict:
    """Structured shift-handoff summary (§11.8): per-queue open/breach counts + active safe modes.

    Alert-fatigue-aware: reports queue-level aggregates + read-back items (breaches), never a flood
    of per-item alerts."""
    now = now or utcnow()
    board = await ops_report(session, now=now)
    from src.services.governance.safe_mode_service import active_states

    safe_modes = await active_states(session)
    breaches = [
        {"queue": q["name"], "id": i["id"], "label": i["label"], "age_hours": i["age_hours"]}
        for q in board["queues"]
        for i in q["items"]
        if i["sla_status"] == "breached"
    ]
    return {
        "generated_at": now.isoformat(),
        "health": board["health"],
        "queue_counts": {
            q["name"]: {"open": q["open"], "breached": q["breached"]} for q in board["queues"]
        },
        "sla_breaches_read_back": breaches,
        "active_safe_modes": [
            f"{s.scopeType}:{s.scopeValue}" if s.scopeValue else s.scopeType for s in safe_modes
        ],
        "roles": list(ROLES),
    }


def owners_matrix() -> list[dict[str, Any]]:
    """The static queue-ownership matrix (owner/backup/role/SLA) — no DB read."""
    return [
        {
            "queue": q.name,
            "description": q.description,
            "owner": q.owner,
            "backup": q.backup,
            "role": q.role,
            "sla_hours": q.sla_hours,
            "source": q.source,
        }
        for q in QUEUES_BY_NAME.values()
    ]

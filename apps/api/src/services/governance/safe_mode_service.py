"""Persisted, scoped safe-mode service (§11.7).

DB-backed so it is fleet-wide + survives restart. Global safe mode freezes everything; scoped safe
modes freeze by venture / jurisdiction / forge / department / tool_class. `covering_state` answers
"is any active safe mode freezing THIS action?" for the PDP. An auto-trigger raises a scoped safe
mode when compliance failures spike.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.run import Run
from src.models.safe_mode import SCOPE_TYPES, SafeModeState
from src.models.scorecard import Scorecard
from src.utils.time import utcnow


class SafeModeError(Exception):
    """Invalid safe-mode operation (bad scope type)."""


# Auto-trigger threshold (§11.7): ≥N compliance failures within the window → scoped safe mode.
_AUTO_FAILURE_THRESHOLD = 5
_AUTO_WINDOW_MINUTES = 60


@dataclass
class ScopeContext:
    """The scope attributes of an action, matched against active safe-mode rows."""

    forge: str | None = None
    department: str | None = None
    venture: str | None = None
    jurisdiction: str | None = None
    tool_class: str | None = None


async def activate(
    session: AsyncSession,
    *,
    scope_type: str = "global",
    scope_value: str = "",
    reason: str = "",
    actor: str = "admin",
    auto: bool = False,
) -> SafeModeState:
    if scope_type not in SCOPE_TYPES:
        raise SafeModeError(f"scope_type must be one of {SCOPE_TYPES}")
    # Dedup: if an active row for this scope exists, return it (idempotent).
    existing = (
        await session.execute(
            select(SafeModeState).where(
                SafeModeState.active.is_(True),
                SafeModeState.scopeType == scope_type,
                SafeModeState.scopeValue == scope_value,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = SafeModeState(
        scopeType=scope_type,
        scopeValue=scope_value,
        active=True,
        reason=reason,
        activatedBy=actor,
        autoTriggered=auto,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def deactivate(
    session: AsyncSession,
    *,
    scope_type: str = "global",
    scope_value: str = "",
    actor: str = "admin",
) -> int:
    """Deactivate all active rows matching a scope. Returns how many were cleared."""
    rows = (
        (
            await session.execute(
                select(SafeModeState).where(
                    SafeModeState.active.is_(True),
                    SafeModeState.scopeType == scope_type,
                    SafeModeState.scopeValue == scope_value,
                )
            )
        )
        .scalars()
        .all()
    )
    now = utcnow()
    for r in rows:
        r.active = False
        r.deactivatedAt = now
        r.deactivatedBy = actor
    if rows:
        await session.commit()
    return len(rows)


async def active_states(session: AsyncSession) -> list[SafeModeState]:
    return list(
        (
            await session.execute(
                select(SafeModeState)
                .where(SafeModeState.active.is_(True))
                .order_by(SafeModeState.activatedAt.desc())
            )
        )
        .scalars()
        .all()
    )


def _matches(row: SafeModeState, scope: ScopeContext) -> bool:
    if row.scopeType == "global":
        return True
    value = {
        "forge": scope.forge,
        "department": scope.department,
        "venture": scope.venture,
        "jurisdiction": scope.jurisdiction,
        "tool_class": scope.tool_class,
    }.get(row.scopeType)
    return value is not None and value == row.scopeValue


async def covering_state(session: AsyncSession, scope: ScopeContext) -> SafeModeState | None:
    """The first active safe-mode row that freezes this action's scope (global always covers)."""
    for row in await active_states(session):
        if _matches(row, scope):
            return row
    return None


async def status(session: AsyncSession) -> dict:
    rows = await active_states(session)
    first = rows[0] if rows else None
    domains = [
        (f"{r.scopeType}:{r.scopeValue}" if r.scopeValue else r.scopeType) for r in rows
    ]
    return {
        "active": bool(rows),
        "global_active": any(r.scopeType == "global" for r in rows),
        # Back-compat fields for the incident dashboard (§10.4 / ADR-0040).
        "reason": first.reason if first else None,
        "activated_by": first.activatedBy if first else None,
        "domains": domains,
        "states": [
            {
                "id": r.id,
                "scope_type": r.scopeType,
                "scope_value": r.scopeValue,
                "reason": r.reason,
                "activated_by": r.activatedBy,
                "activated_at": r.activatedAt.isoformat() if r.activatedAt else None,
                "auto_triggered": r.autoTriggered,
            }
            for r in rows
        ],
    }


async def maybe_auto_activate(session: AsyncSession) -> SafeModeState | None:
    """§11.7 auto-trigger: ≥5 compliance failures in 1h across the Village → scoped safe mode.

    A failure spike freezes globally pending review. Idempotent via activate() dedup."""
    since = utcnow() - timedelta(minutes=_AUTO_WINDOW_MINUTES)
    rows = (
        await session.execute(
            select(Run, Scorecard)
            .join(Scorecard, Scorecard.runId == Run.id)
            .where(Run.startedAt >= since, Scorecard.p2Compliance.is_(False))
        )
    ).all()
    if len(rows) < _AUTO_FAILURE_THRESHOLD:
        return None
    # Attribute failures to a forge (from the run's scenario caps is heavy; use action-agnostic
    # global scope for the safety net — a failure spike freezes everything pending review).
    return await activate(
        session,
        scope_type="global",
        scope_value="",
        reason=f"auto: {len(rows)} compliance failures in {_AUTO_WINDOW_MINUTES}m",
        actor="auto-safe-mode",
        auto=True,
    )

"""Revoke an OperationCertification and record it, append-only (ADR-0158).

The existing revoke paths in `recert.py` overwrite `state` and keep nothing of what it was. This one
writes an `OperationCertificationEvent` first, holding the prior state, the actor and the reason,
then sets `state` to `revoked`. Every reader of `OperationCertification` sees the revocation: a
superseding row would not do, because `coverage`, `capacity` and `module_has_any_certified_agent`
count every row, not only the latest.

Does not commit. The caller commits, so a batch either lands whole or not at all.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_cert import OperationCertification, OperationCertificationEvent
from src.services.operation.state_machine import OperationState


async def revoke_operation_certification(
    session: AsyncSession, cert: OperationCertification, *, reason: str, actor: str
) -> OperationCertificationEvent | None:
    """Revoke `cert` with a recorded reason. None if it is already revoked: nothing to record."""
    if cert.state == OperationState.REVOKED.value:
        return None
    if not reason.strip() or not actor.strip():
        raise ValueError("a revocation needs a reason and an actor")
    event = OperationCertificationEvent(
        operationCertificationId=cert.id,
        event="revoked",
        fromState=cert.state,
        toState=OperationState.REVOKED.value,
        actor=actor,
        reason=reason,
    )
    session.add(event)
    cert.state = OperationState.REVOKED.value
    return event

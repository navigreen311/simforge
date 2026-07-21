"""Cert lifecycle worker (blueprint §C.5, queue `cert-lifecycle`, nightly 02:00 UTC).

Sweeps for certs expiring soon (renewal nudge) and past-due certs (mark expired).
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import SessionLocal, dispose_engine
from src.models.cert import AgentCert, CertLifecycleEvent
from src.telemetry.logging import get_logger
from src.utils.time import utcnow

log = get_logger("cert_lifecycle_worker")


async def _sweep(session: AsyncSession) -> dict:
    now = utcnow()
    soon = now + timedelta(days=7)

    expiring = (
        (
            await session.execute(
                select(AgentCert).where(
                    AgentCert.status == "active",
                    AgentCert.expiresAt < soon,
                    AgentCert.expiresAt >= now,
                )
            )
        )
        .scalars()
        .all()
    )
    expired = (
        (
            await session.execute(
                select(AgentCert).where(AgentCert.status == "active", AgentCert.expiresAt < now)
            )
        )
        .scalars()
        .all()
    )
    for cert in expired:
        cert.status = "expired"
        session.add(
            CertLifecycleEvent(agentCertId=cert.id, event="expired", timestamp=now, actor="system")
        )
    await session.commit()
    return {"expiring_soon": len(expiring), "expired": len(expired)}


async def _run() -> dict:
    async with SessionLocal() as session:
        result = await _sweep(session)
    log.info("cert_lifecycle_sweep", **result)
    await dispose_engine()
    return result


def run_cert_lifecycle_sweep() -> dict:
    """Synchronous entrypoint for RQ."""
    return asyncio.run(_run())

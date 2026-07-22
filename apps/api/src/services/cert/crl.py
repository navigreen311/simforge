"""Certificate Revocation List (blueprint §C.3.14; ADR-0038).

A signed CertSnapshot is valid evidence *unless the cert has been revoked or suspended* — a
governance action (revocation, constitution-amendment auto-suspend, forge-drift suspend, training
re-cert suspend) that invalidates an otherwise-verifiable signature. External verifiers therefore
need a published CRL: given a snapshot id, is this cert still honoured?

Expiry is **not** in the CRL — it is time-based and self-evident from `expiresAt`. The CRL carries
only governance-invalidated certs (`revoked` | `suspended`), each with the reason and timestamp from
its lifecycle event.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cert import AgentCert, CertLifecycleEvent, CertSnapshot

_INVALIDATED = ("revoked", "suspended")


async def build_crl(session: AsyncSession) -> list[dict]:
    """Structured CRL entries for every governance-invalidated cert, newest action first."""
    certs = (
        (await session.execute(select(AgentCert).where(AgentCert.status.in_(_INVALIDATED))))
        .scalars()
        .all()
    )
    if not certs:
        return []

    snap_by_id = {
        s.id: s
        for s in (
            await session.execute(
                select(CertSnapshot).where(CertSnapshot.id.in_([c.certSnapshotId for c in certs]))
            )
        )
        .scalars()
        .all()
    }

    entries: list[dict] = []
    for cert in certs:
        snap = snap_by_id.get(cert.certSnapshotId)
        # The lifecycle event that put the cert in its current (invalidated) state.
        event = (
            await session.execute(
                select(CertLifecycleEvent)
                .where(CertLifecycleEvent.agentCertId == cert.id)
                .where(CertLifecycleEvent.event == cert.status)
                .order_by(CertLifecycleEvent.timestamp.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        entries.append(
            {
                "cert_id": cert.id,
                "snapshot_id": snap.snapshotId if snap else None,
                "forge_cap": cert.forgeCap,
                "status": cert.status,
                "reason": (event.reason if event else None) or cert.revocationReason,
                "at": (event.timestamp if event else cert.revokedAt),
            }
        )

    entries.sort(key=lambda e: (e["at"] is not None, e["at"]), reverse=True)
    return entries


async def crl_snapshot_ids(session: AsyncSession) -> list[str]:
    """The flat list of revoked/suspended snapshot ids — the CRL as published in /public-keys."""
    return [e["snapshot_id"] for e in await build_crl(session) if e["snapshot_id"]]

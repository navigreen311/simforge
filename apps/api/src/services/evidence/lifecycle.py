"""Evidence lifecycle (§12.3): Merkle chain-of-custody, retention, legal hold, redaction, access
audit, and purge.

`register_evidence` records a stored bundle and chains it onto the tamper-evident Merkle ledger.
`verify_chain` recomputes the chain to detect tampering. Redaction classes gate external export;
legal hold blocks purge; every access is logged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.evidence import REDACTION_CLASSES, EvidenceAccess, EvidenceRecord
from src.utils.time import utcnow

# Default retention: 7 years (HIPAA-adjacent), configurable per pack later.
_DEFAULT_RETENTION_DAYS = 365 * 7

# Fields stripped per redaction class on external-auditor export.
_REDACT_KEYS = {
    "standard": (),
    "pii": ("agent", "subject", "approver_id"),
    "financial": ("cost_usd", "tokens_used", "pinned_versions"),
    "phi_synthetic": ("transcript", "subject", "agent", "battery"),
}


def _anchor(prev_anchor: str | None, content_hash: str) -> str:
    return hashlib.sha256(((prev_anchor or "") + content_hash).encode()).hexdigest()


@dataclass
class ChainStatus:
    intact: bool
    length: int
    break_at: str | None  # bundleId where the chain first fails, if any


async def _tail(session: AsyncSession) -> EvidenceRecord | None:
    """The chain tail — the record whose chainAnchor no other record points at as its prevAnchor.

    Order-independent (doesn't rely on createdAt, which can tie in fast runs); the chain is a real
    linked list keyed on the Merkle anchors."""
    records = list((await session.execute(select(EvidenceRecord))).scalars().all())
    if not records:
        return None
    referenced = {r.prevAnchor for r in records if r.prevAnchor is not None}
    tails = [r for r in records if r.chainAnchor not in referenced]
    if len(tails) == 1:
        return tails[0]
    # Degenerate (fork/empty) — fall back to the most recent by created time.
    return max(records, key=lambda r: r.createdAt)


async def register_evidence(
    session: AsyncSession,
    *,
    bundle_id: str,
    ref: str,
    content_hash: str,
    redaction_class: str = "standard",
    retention_days: int | None = None,
    pack_id: str | None = None,
) -> EvidenceRecord:
    """Record a stored bundle + chain it onto the Merkle ledger. Idempotent per bundle_id."""
    existing = (
        await session.execute(select(EvidenceRecord).where(EvidenceRecord.bundleId == bundle_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    if redaction_class not in REDACTION_CLASSES:
        redaction_class = "standard"
    prev = await _tail(session)
    prev_anchor = prev.chainAnchor if prev else None
    now = utcnow()
    days = retention_days if retention_days is not None else _DEFAULT_RETENTION_DAYS
    rec = EvidenceRecord(
        bundleId=bundle_id,
        ref=ref,
        contentHash=content_hash,
        prevAnchor=prev_anchor,
        chainAnchor=_anchor(prev_anchor, content_hash),
        redactionClass=redaction_class,
        tier="hot",
        retentionUntil=now + timedelta(days=days),
        legalHold=False,
        packId=pack_id,
    )
    session.add(rec)
    # Flush (not commit): register_evidence runs inside the cert-issuance transaction; the caller's
    # commit finalizes. Standalone callers (API) commit themselves.
    await session.flush()
    return rec


async def verify_chain(session: AsyncSession) -> ChainStatus:
    """Walk the Merkle chain from genesis via prevAnchor links; report the first break (tamper).

    Order-independent: follows the linked list rather than sorting by time, so it is stable even
    when records share a createdAt timestamp."""
    records = list((await session.execute(select(EvidenceRecord))).scalars().all())
    total = len(records)
    if total == 0:
        return ChainStatus(True, 0, None)
    by_prev: dict[str | None, EvidenceRecord] = {r.prevAnchor: r for r in records}
    prev_anchor: str | None = None
    seen = 0
    while prev_anchor in by_prev:
        rec = by_prev[prev_anchor]
        expected = _anchor(prev_anchor, rec.contentHash)
        if rec.chainAnchor != expected:
            return ChainStatus(False, total, rec.bundleId)
        prev_anchor = rec.chainAnchor
        seen += 1
        if seen > total:  # cycle guard
            return ChainStatus(False, total, rec.bundleId)
    if seen != total:
        # A record exists that the walk never reached → a broken/forked link.
        reached = set()
        p: str | None = None
        while p in by_prev and by_prev[p].chainAnchor not in reached:
            reached.add(by_prev[p].chainAnchor)
            p = by_prev[p].chainAnchor
        missing = next((r.bundleId for r in records if r.chainAnchor not in reached), None)
        return ChainStatus(False, total, missing)
    return ChainStatus(True, total, None)


async def log_access(
    session: AsyncSession, bundle_id: str, accessor: str, reason: str
) -> EvidenceAccess | None:
    rec = (
        await session.execute(select(EvidenceRecord).where(EvidenceRecord.bundleId == bundle_id))
    ).scalar_one_or_none()
    if rec is None:
        return None
    access = EvidenceAccess(recordId=rec.id, accessor=accessor, reason=reason)
    session.add(access)
    await session.commit()
    await session.refresh(access)
    return access


async def set_legal_hold(
    session: AsyncSession, bundle_id: str, hold: bool, actor: str
) -> EvidenceRecord | None:
    rec = (
        await session.execute(select(EvidenceRecord).where(EvidenceRecord.bundleId == bundle_id))
    ).scalar_one_or_none()
    if rec is None:
        return None
    rec.legalHold = hold
    await session.commit()
    await session.refresh(rec)
    return rec


async def purge_expired(session: AsyncSession, *, now: datetime | None = None) -> list[str]:
    """Mark records past retention as purged — UNLESS on legal hold. Returns purged bundle ids."""
    cutoff = now or utcnow()
    stale = (
        (
            await session.execute(
                select(EvidenceRecord).where(
                    EvidenceRecord.retentionUntil < cutoff,
                    EvidenceRecord.legalHold.is_(False),
                    EvidenceRecord.purgedAt.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for rec in stale:
        rec.purgedAt = cutoff
        rec.tier = "cold"
    if stale:
        await session.commit()
    return [r.bundleId for r in stale]


def redact_bundle(bundle: dict, redaction_class: str) -> dict:
    """Return an export copy with fields removed per the redaction class (§12.3)."""
    keys = _REDACT_KEYS.get(redaction_class, ())
    return {k: ("[REDACTED]" if k in keys else v) for k, v in bundle.items()}


def default_redaction_for(pack_phi_required: bool) -> str:
    return "phi_synthetic" if pack_phi_required else "standard"


async def evidence_status(session: AsyncSession) -> dict:
    records = list((await session.execute(select(EvidenceRecord))).scalars().all())
    chain = await verify_chain(session)
    return {
        "total": len(records),
        "chain_intact": chain.intact,
        "chain_length": chain.length,
        "chain_break_at": chain.break_at,
        "on_legal_hold": sum(1 for r in records if r.legalHold),
        "purged": sum(1 for r in records if r.purgedAt is not None),
        "retention_years": settings_retention_years(),
    }


def settings_retention_years() -> int:
    return _DEFAULT_RETENTION_DAYS // 365

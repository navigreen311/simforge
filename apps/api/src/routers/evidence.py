"""Evidence lifecycle router (§12.3) — chain integrity, legal hold, access audit, export."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.evidence import EvidenceAccess, EvidenceRecord
from src.services.evidence import (
    evidence_status,
    log_access,
    purge_expired,
    redact_bundle,
    set_legal_hold,
    verify_chain,
)

router = APIRouter()


class LegalHoldRequest(BaseModel):
    hold: bool
    actor: str = "counsel"


def _record_out(r: EvidenceRecord) -> dict:
    return {
        "bundle_id": r.bundleId,
        "content_hash": r.contentHash,
        "chain_anchor": r.chainAnchor,
        "redaction_class": r.redactionClass,
        "tier": r.tier,
        "retention_until": r.retentionUntil.isoformat() if r.retentionUntil else None,
        "legal_hold": r.legalHold,
        "purged_at": r.purgedAt.isoformat() if r.purgedAt else None,
    }


@router.get("/status", dependencies=[Depends(require_role("viewer"))])
async def status_endpoint(session: AsyncSession = Depends(get_session)) -> dict:
    return await evidence_status(session)


@router.get("/chain/verify", dependencies=[Depends(require_role("viewer"))])
async def chain_verify(session: AsyncSession = Depends(get_session)) -> dict:
    chain = await verify_chain(session)
    return {"intact": chain.intact, "length": chain.length, "break_at": chain.break_at}


@router.get("/{bundle_id}", dependencies=[Depends(require_role("viewer"))])
async def get_record(bundle_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    r = (
        await session.execute(select(EvidenceRecord).where(EvidenceRecord.bundleId == bundle_id))
    ).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    accesses = (
        (
            await session.execute(
                select(EvidenceAccess)
                .where(EvidenceAccess.recordId == r.id)
                .order_by(EvidenceAccess.at.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        **_record_out(r),
        "access_log": [
            {"accessor": a.accessor, "reason": a.reason, "at": a.at.isoformat()} for a in accesses
        ],
    }


@router.post("/{bundle_id}/legal-hold", dependencies=[Depends(require_role("compliance_analyst"))])
async def legal_hold(
    bundle_id: str, body: LegalHoldRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    r = await set_legal_hold(session, bundle_id, body.hold, body.actor)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    return _record_out(r)


@router.get("/{bundle_id}/export", dependencies=[Depends(require_role("compliance_analyst"))])
async def export_redacted(
    bundle_id: str,
    accessor: str = Query(default="auditor"),
    reason: str = Query(default="external audit"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Redacted external-auditor export: applies the record's redaction class + logs the access."""
    r = (
        await session.execute(select(EvidenceRecord).where(EvidenceRecord.bundleId == bundle_id))
    ).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    await log_access(session, bundle_id, accessor, reason)
    # Load the stored bundle (dev: file://) and redact it.
    bundle: dict = {}
    try:
        parsed = urlparse(r.ref)
        if parsed.scheme == "file":
            bundle = json.loads(Path(url2pathname(parsed.path)).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a missing local file shouldn't 500 the export
        bundle = {"note": "bundle payload unavailable in this environment", "ref": r.ref}
    return {
        "bundle_id": bundle_id,
        "redaction_class": r.redactionClass,
        "redacted_bundle": redact_bundle(bundle, r.redactionClass),
    }


@router.post("/purge-expired", dependencies=[Depends(require_role("admin"))])
async def purge(session: AsyncSession = Depends(get_session)) -> dict:
    purged = await purge_expired(session)
    return {"purged": purged, "count": len(purged)}

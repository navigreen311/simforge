"""External attestation router (blueprint §C.3.14).

Public-facing (viewer) verification of certification status + published signing keys/CRL.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.cert import AgentCert, CertSnapshot
from src.schemas.cert import AttestResponse, PublicKeyOut, PublicKeysResponse
from src.services.cert import get_signer, verify_snapshot
from src.services.cert.crl import build_crl, crl_snapshot_ids

router = APIRouter()


@router.get(
    "/cert/{cert_id}", response_model=AttestResponse, dependencies=[Depends(require_role("viewer"))]
)
async def attest_cert(cert_id: str, session: AsyncSession = Depends(get_session)) -> AttestResponse:
    cert = (
        await session.execute(select(AgentCert).where(AgentCert.id == cert_id))
    ).scalar_one_or_none()
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cert not found")
    snap = (
        await session.execute(select(CertSnapshot).where(CertSnapshot.id == cert.certSnapshotId))
    ).scalar_one()
    verify = verify_snapshot(snap)
    return AttestResponse(
        cert_id=cert.id,
        subject=snap.subject,
        forge_cap=cert.forgeCap,
        tier=cert.tier,
        status=cert.status,
        expires_at=cert.expiresAt,
        snapshot_id=snap.snapshotId,
        signature_valid=verify.valid,
    )


@router.get("/public-keys", response_model=PublicKeysResponse)
async def public_keys(session: AsyncSession = Depends(get_session)) -> PublicKeysResponse:
    """Published signing keys + the CRL (revoked/suspended snapshot ids) for external verifiers."""
    signer = get_signer()
    return PublicKeysResponse(
        keys=[PublicKeyOut(key_id=signer.key_id(), public_key_pem=signer.public_key_pem())],
        crl=await crl_snapshot_ids(session),
    )


@router.get("/crl", dependencies=[Depends(require_role("viewer"))])
async def crl(session: AsyncSession = Depends(get_session)) -> dict:
    """The full CRL — every governance-invalidated cert with its reason + timestamp."""
    entries = await build_crl(session)
    return {"entries": entries, "total": len(entries)}

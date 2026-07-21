"""Certs router (blueprint §C.3.7). Issue is Ivan-only (admin); audited."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.cert import AgentCert, CertSnapshot
from src.schemas.cert import (
    AgentCertList,
    AgentCertOut,
    CertSnapshotOut,
    IssueAgentCertRequest,
    IssueCertResponse,
    RevokeCertRequest,
    VerifyResponse,
)
from src.services.cert import (
    CertIssuanceError,
    issue_agent_cert,
    revoke_agent_cert,
    verify_snapshot,
)

router = APIRouter()


@router.post(
    "/agent/issue",
    response_model=IssueCertResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def issue_cert(
    body: IssueAgentCertRequest, session: AsyncSession = Depends(get_session)
) -> IssueCertResponse:
    try:
        issued = await issue_agent_cert(
            session,
            agent_village_id=body.agent_village_id,
            forge_cap=body.forge_cap,
            tier=body.tier,
            battery_run_ids=body.battery_run_ids,
            approver_id=body.approver_id,
            pack_id=body.pack_id,
        )
    except CertIssuanceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return IssueCertResponse(
        cert=AgentCertOut.model_validate(issued.agent_cert),
        snapshot=CertSnapshotOut.model_validate(issued.snapshot),
        autonomy_from=issued.autonomy_from,
        autonomy_to=issued.autonomy_to,
    )


@router.get("/agent", response_model=AgentCertList, dependencies=[Depends(require_role("viewer"))])
async def list_agent_certs(
    session: AsyncSession = Depends(get_session),
    cert_status: str | None = Query(default=None, alias="status"),
) -> AgentCertList:
    stmt = select(AgentCert)
    count_stmt = select(func.count()).select_from(AgentCert)
    if cert_status:
        stmt = stmt.where(AgentCert.status == cert_status)
        count_stmt = count_stmt.where(AgentCert.status == cert_status)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.order_by(AgentCert.issuedAt.desc()))).scalars().all()
    return AgentCertList(items=[AgentCertOut.model_validate(r) for r in rows], total=total)


@router.get(
    "/agent/{cert_id}", response_model=AgentCertOut, dependencies=[Depends(require_role("viewer"))]
)
async def get_agent_cert(
    cert_id: str, session: AsyncSession = Depends(get_session)
) -> AgentCertOut:
    cert = (
        await session.execute(select(AgentCert).where(AgentCert.id == cert_id))
    ).scalar_one_or_none()
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cert not found")
    return AgentCertOut.model_validate(cert)


@router.post(
    "/agent/{cert_id}/revoke",
    response_model=AgentCertOut,
    dependencies=[Depends(require_role("admin"))],
)
async def revoke_cert(
    cert_id: str, body: RevokeCertRequest, session: AsyncSession = Depends(get_session)
) -> AgentCertOut:
    try:
        cert = await revoke_agent_cert(session, cert_id, body.reason, actor="admin")
    except CertIssuanceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AgentCertOut.model_validate(cert)


# --- snapshots (mounted under /api/snapshots via a separate include) ---
snapshots_router = APIRouter()


@snapshots_router.get(
    "/{snapshot_id}", response_model=CertSnapshotOut, dependencies=[Depends(require_role("viewer"))]
)
async def get_snapshot(
    snapshot_id: str, session: AsyncSession = Depends(get_session)
) -> CertSnapshotOut:
    snap = (
        await session.execute(select(CertSnapshot).where(CertSnapshot.snapshotId == snapshot_id))
    ).scalar_one_or_none()
    if snap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    return CertSnapshotOut.model_validate(snap)


@snapshots_router.get(
    "/{snapshot_id}/verify",
    response_model=VerifyResponse,
    dependencies=[Depends(require_role("viewer"))],
)
async def verify_snapshot_endpoint(
    snapshot_id: str, session: AsyncSession = Depends(get_session)
) -> VerifyResponse:
    snap = (
        await session.execute(select(CertSnapshot).where(CertSnapshot.snapshotId == snapshot_id))
    ).scalar_one_or_none()
    if snap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    result = verify_snapshot(snap)
    return VerifyResponse(
        snapshot_id=snapshot_id, valid=result.valid, key_id=result.key_id, reason=result.reason
    )

"""Certs router (blueprint §C.3.7). Issue is Ivan-only (admin); audited."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.models.cert import AgentCert, CertSnapshot, DeptCert
from src.models.department import Department
from src.schemas.cert import (
    AgentCertList,
    AgentCertOut,
    CertSnapshotOut,
    DeptCertList,
    DeptCertOut,
    DeptPrereqStatusOut,
    IssueAgentCertRequest,
    IssueCertResponse,
    IssueDeptCertRequest,
    IssueDeptCertResponse,
    ReinstateCertRequest,
    RevokeCertRequest,
    VerifyResponse,
)
from src.services.capabilities import describe_capability
from src.services.cert import (
    CertIssuanceError,
    dept_prerequisite_status,
    issue_agent_cert,
    issue_dept_cert,
    reinstate_agent_cert,
    revoke_agent_cert,
    revoke_dept_cert,
    verify_snapshot,
)

router = APIRouter()


def _with_capability(cert: AgentCert) -> AgentCertOut:
    """Attach the derived plain-language capability label (same catalog as the Readiness Matrix)."""
    out = AgentCertOut.model_validate(cert)
    d = describe_capability(cert.forgeCap)
    out.capabilityLabel = d["label"]
    out.capabilityForge = d["forge"]
    out.capabilityDescription = d["description"]
    return out


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
    from src.telemetry.metrics import CERTS_ISSUED_TOTAL

    CERTS_ISSUED_TOTAL.labels(tier=issued.agent_cert.tier).inc()
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
    tier: str | None = Query(default=None),
    forge: str | None = Query(default=None, description="Match the forge prefix of forgeCap"),
    agent: str | None = Query(default=None, description="Filter by tested agent villageAgentId"),
    expiring_within: int | None = Query(default=None, ge=1, description="Days-to-expiry window"),
    search: str | None = Query(default=None, description="Match forgeCap / cert id"),
) -> AgentCertList:
    from datetime import timedelta

    from src.models.agent import Agent
    from src.utils.time import utcnow

    stmt = select(AgentCert)
    count_stmt = select(func.count()).select_from(AgentCert)

    def _apply(s):  # noqa: ANN001, ANN202
        if cert_status:
            s = s.where(AgentCert.status == cert_status)
        if tier:
            s = s.where(AgentCert.tier == tier)
        if forge:
            s = s.where(AgentCert.forgeCap.like(f"{forge}.%"))
        if agent:
            s = s.where(
                AgentCert.agentId.in_(select(Agent.id).where(Agent.villageAgentId == agent))
            )
        if expiring_within is not None:
            s = s.where(AgentCert.expiresAt <= utcnow() + timedelta(days=expiring_within))
        if search:
            like = f"%{search.lower()}%"
            s = s.where(
                func.lower(AgentCert.forgeCap).like(like) | func.lower(AgentCert.id).like(like)
            )
        return s

    total = (await session.execute(_apply(count_stmt))).scalar_one()
    rows = (await session.execute(_apply(stmt).order_by(AgentCert.issuedAt.desc()))).scalars().all()
    return AgentCertList(items=[_with_capability(r) for r in rows], total=total)


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
    return _with_capability(cert)


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


@router.post(
    "/agent/{cert_id}/reinstate",
    response_model=IssueCertResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def reinstate_cert(
    cert_id: str, body: ReinstateCertRequest, session: AsyncSession = Depends(get_session)
) -> IssueCertResponse:
    """Reinstate a suspended cert by re-certifying against the current version matrix."""
    try:
        issued = await reinstate_agent_cert(
            session, cert_id, body.battery_run_ids, body.approver_id
        )
    except CertIssuanceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return IssueCertResponse(
        cert=AgentCertOut.model_validate(issued.agent_cert),
        snapshot=CertSnapshotOut.model_validate(issued.snapshot),
        autonomy_from=issued.autonomy_from,
        autonomy_to=issued.autonomy_to,
    )


# --- DeptCerts (department × forge-context composite; D2 dual certification) ---


async def _dept_out(session: AsyncSession, cert: DeptCert) -> DeptCertOut:
    out = DeptCertOut.model_validate(cert)
    dept = (
        await session.execute(select(Department).where(Department.id == cert.departmentId))
    ).scalar_one_or_none()
    out.departmentKey = dept.villageKey if dept else ""
    return out


@router.get(
    "/dept/prerequisites",
    response_model=DeptPrereqStatusOut,
    dependencies=[Depends(require_role("viewer"))],
)
async def dept_prereqs(
    department_key: str = Query(...),
    forge_caps: str | None = Query(default=None, description="Comma-separated required forge caps"),
    session: AsyncSession = Depends(get_session),
) -> DeptPrereqStatusOut:
    """Whether a department has enough covering AgentCerts to issue a DeptCert (blast preview)."""
    caps = [c for c in (forge_caps.split(",") if forge_caps else []) if c]
    try:
        status_obj = await dept_prerequisite_status(session, department_key, caps)
    except CertIssuanceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DeptPrereqStatusOut(**status_obj.as_dict())


@router.get("/dept", response_model=DeptCertList, dependencies=[Depends(require_role("viewer"))])
async def list_dept_certs(
    department_key: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> DeptCertList:
    stmt = select(DeptCert).order_by(DeptCert.issuedAt.desc())
    if department_key:
        dept = (
            await session.execute(select(Department).where(Department.villageKey == department_key))
        ).scalar_one_or_none()
        stmt = stmt.where(DeptCert.departmentId == (dept.id if dept else "none"))
    if status_filter:
        stmt = stmt.where(DeptCert.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    items = [await _dept_out(session, c) for c in rows]
    return DeptCertList(items=items, total=len(items))


@router.post(
    "/dept/issue",
    response_model=IssueDeptCertResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def issue_dept(
    body: IssueDeptCertRequest, session: AsyncSession = Depends(get_session)
) -> IssueDeptCertResponse:
    try:
        issued = await issue_dept_cert(
            session,
            department_key=body.department_key,
            forge_context=body.forge_context,
            tier=body.tier,
            dept_battery_run_ids=body.dept_battery_run_ids,
            approver_id=body.approver_id,
            pack_id=body.pack_id,
            required_forge_caps=body.required_forge_caps,
            prerequisite_min=body.prerequisite_min,
        )
    except CertIssuanceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return IssueDeptCertResponse(
        cert=await _dept_out(session, issued.dept_cert),
        snapshot=CertSnapshotOut.model_validate(issued.snapshot),
    )


@router.post(
    "/dept/{cert_id}/revoke",
    response_model=DeptCertOut,
    dependencies=[Depends(require_role("admin"))],
)
async def revoke_dept(
    cert_id: str, body: RevokeCertRequest, session: AsyncSession = Depends(get_session)
) -> DeptCertOut:
    try:
        cert = await revoke_dept_cert(session, cert_id, body.reason, actor="admin")
    except CertIssuanceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return await _dept_out(session, cert)


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

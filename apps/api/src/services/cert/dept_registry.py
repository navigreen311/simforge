"""Department certification registry — issue/revoke DeptCerts + prerequisite coverage (§3.1, §5.3,
§11.1, §11.3).

A DeptCert certifies one Village-department × one Forge-context, composed hierarchically from the
department's AgentCerts. Spec preconditions for issuance:
  - ≥ N distinct agents in the department hold active AgentCerts for the context's forge-caps
    (N default = `dept_min_agent_certs`, Pack-configurable).
  - Department-wide multi-agent scenarios passed at Intermediate tier or higher.
  - Aggregate P2 Compliance across those dept scenarios = 100%.
Revocation is automatic when AgentCert coverage drops below the minimum (prerequisite-dependency
failure — Revocation trigger #3), or manual. Mirrors the AgentCert lifecycle (append-only
CertLifecycleEvent, signed CertSnapshot, lineage edges).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.agent import Agent
from src.models.cert import AgentCert, CertLifecycleEvent, CertSnapshot, DeptCert
from src.models.department import Department
from src.models.pack import Pack, Scenario
from src.models.run import Run
from src.models.scorecard import Scorecard
from src.services.cert.registry import CertIssuanceError
from src.services.cert.signer import encode_signature, get_signer
from src.services.cert.snapshot import CertSnapshotPayload, PinnedVersions
from src.services.evidence import store_evidence_bundle
from src.utils.time import utcnow

# Tiers that count as "Intermediate or higher" for dept-wide scenarios (§5.3 DeptCert condition).
_INTERMEDIATE_PLUS = {"intermediate", "advanced_crisis"}


@dataclass
class DeptPrereqStatus:
    department_key: str
    required_min: int
    required_forge_caps: list[str]
    covering_agents: list[str]  # distinct agents holding an active relevant AgentCert
    satisfied: bool

    def as_dict(self) -> dict:
        return {
            "department_key": self.department_key,
            "required_min": self.required_min,
            "required_forge_caps": self.required_forge_caps,
            "covering_agents": self.covering_agents,
            "covering_count": len(self.covering_agents),
            "satisfied": self.satisfied,
        }


@dataclass
class IssuedDeptCert:
    dept_cert: DeptCert
    snapshot: CertSnapshot
    prerequisite_agent_cert_ids: list[str] = field(default_factory=list)


async def _department(session: AsyncSession, department_key: str) -> Department:
    dept = (
        await session.execute(select(Department).where(Department.villageKey == department_key))
    ).scalar_one_or_none()
    if dept is None:
        raise CertIssuanceError(f"Department not found: {department_key}")
    return dept


async def dept_prerequisite_status(
    session: AsyncSession,
    department_key: str,
    required_forge_caps: list[str] | None = None,
    prerequisite_min: int | None = None,
) -> DeptPrereqStatus:
    """How many distinct agents in the department hold an active AgentCert covering the context.

    `required_forge_caps` empty → any active AgentCert in the department counts (a plain N-certified
    agents rule); non-empty → only certs for those caps count."""
    dept = await _department(session, department_key)
    minimum = prerequisite_min if prerequisite_min is not None else settings.dept_min_agent_certs
    caps = required_forge_caps or []

    agent_ids = {
        a.id
        for a in (
            await session.execute(select(Agent).where(Agent.departmentId == dept.id))
        ).scalars()
    }
    stmt = select(AgentCert).where(
        AgentCert.agentId.in_(agent_ids or {"none"}), AgentCert.status == "active"
    )
    if caps:
        stmt = stmt.where(AgentCert.forgeCap.in_(caps))
    certs = (await session.execute(stmt)).scalars().all()

    agent_vid = {
        a.id: a.villageAgentId
        for a in (
            await session.execute(select(Agent).where(Agent.id.in_(agent_ids or {"none"})))
        ).scalars()
    }
    covering = sorted({agent_vid.get(c.agentId, c.agentId) for c in certs})
    return DeptPrereqStatus(
        department_key=department_key,
        required_min=minimum,
        required_forge_caps=caps,
        covering_agents=covering,
        satisfied=len(covering) >= minimum,
    )


async def _covering_cert_ids(
    session: AsyncSession, department_id: str, required_forge_caps: list[str]
) -> list[str]:
    agent_ids = {
        a.id
        for a in (
            await session.execute(select(Agent).where(Agent.departmentId == department_id))
        ).scalars()
    }
    stmt = select(AgentCert).where(
        AgentCert.agentId.in_(agent_ids or {"none"}), AgentCert.status == "active"
    )
    if required_forge_caps:
        stmt = stmt.where(AgentCert.forgeCap.in_(required_forge_caps))
    return [c.id for c in (await session.execute(stmt)).scalars().all()]


async def _validate_dept_battery(
    session: AsyncSession, dept_battery_run_ids: list[str]
) -> list[Run]:
    """Dept-wide scenarios must exist, have passed the gate, be Intermediate+, and be P2=100%."""
    if not dept_battery_run_ids:
        raise CertIssuanceError("A DeptCert requires ≥1 dept-wide scenario run")
    runs: list[Run] = []
    for rid in dept_battery_run_ids:
        run = (await session.execute(select(Run).where(Run.runId == rid))).scalar_one_or_none()
        if run is None:
            raise CertIssuanceError(f"Run not found: {rid}")
        scenario = (
            await session.execute(select(Scenario).where(Scenario.id == run.scenarioId))
        ).scalar_one_or_none()
        if scenario is None or scenario.tier not in _INTERMEDIATE_PLUS:
            raise CertIssuanceError(
                f"Dept scenario {rid} must be Intermediate tier or higher "
                f"(got '{scenario.tier if scenario else 'unknown'}')"
            )
        card = (
            await session.execute(select(Scorecard).where(Scorecard.runId == run.id))
        ).scalar_one_or_none()
        if card is None or not card.readinessGatePassed:
            raise CertIssuanceError(f"Dept scenario {rid} did not pass the readiness gate")
        if card.p2Compliance is not True:
            raise CertIssuanceError(
                f"Dept scenario {rid} failed P2 Compliance (aggregate must be 100%)"
            )
        runs.append(run)
    return runs


async def _create_dept_snapshot(
    session: AsyncSession,
    department_key: str,
    forge_context: str,
    tier: str,
    runs: list[Run],
    approver_id: str,
    pack: Pack,
    prerequisite_cert_ids: list[str],
) -> tuple[CertSnapshot, datetime, datetime]:
    now = utcnow()
    expires = now + timedelta(days=settings.cert_validity_days)
    pinned = PinnedVersions(
        pack=pack.packId,
        scenario_library_hash=pack.yamlHash,
        forge_versions={},
        village_schema_fingerprint="",
    )
    payload = CertSnapshotPayload(
        cert_type="dept_forge_context",
        subject=department_key,
        tier=tier,
        issued_at=now,
        expires_at=expires,
        pinned_versions=pinned.as_dict(),
        evidence_bundle_ref="",
        forge_context=forge_context,
    )
    snapshot_id = f"certsnap:{payload.content_hash()[:16]}"
    bundle = {
        "snapshot_id": snapshot_id,
        "subject": department_key,
        "forge_context": forge_context,
        "tier": tier,
        "approver_id": approver_id,
        "prerequisite_agent_cert_ids": prerequisite_cert_ids,
        "dept_battery": [
            {"run_id": r.runId, "scenario_internal_id": r.scenarioId, "outcome": r.outcome}
            for r in runs
        ],
        "pinned_versions": pinned.as_dict(),
        "issued_at": now,
    }
    evidence_ref = store_evidence_bundle(snapshot_id.replace(":", "_"), bundle)
    payload.evidence_bundle_ref = evidence_ref

    content_hash = payload.content_hash()
    snapshot_id = f"certsnap:{content_hash[:16]}"
    signer = get_signer()
    signature = encode_signature(signer.sign(payload.to_canonical().encode()))
    snapshot = CertSnapshot(
        snapshotId=snapshot_id,
        certType="dept_forge_context",
        subject=department_key,
        forgeContext=forge_context,
        tier=tier,
        issuedAt=now,
        expiresAt=expires,
        pinnedVersions=pinned.as_dict(),
        evidenceBundleRef=evidence_ref,
        signingKeyId=signer.key_id(),
        signature=signature,
        contentHash=content_hash,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot, now, expires


async def issue_dept_cert(
    session: AsyncSession,
    department_key: str,
    forge_context: str,
    tier: str,
    dept_battery_run_ids: list[str],
    approver_id: str,
    pack_id: str,
    required_forge_caps: list[str] | None = None,
    prerequisite_min: int | None = None,
) -> IssuedDeptCert:
    """Issue a DeptCert iff prerequisites hold (§5.3): ≥N covering AgentCerts + dept-wide
    Intermediate+ scenarios passed at P2=100%."""
    dept = await _department(session, department_key)
    caps = required_forge_caps or []
    minimum = prerequisite_min if prerequisite_min is not None else settings.dept_min_agent_certs

    status = await dept_prerequisite_status(session, department_key, caps, minimum)
    if not status.satisfied:
        raise CertIssuanceError(
            f"DeptCert prerequisite unmet: {len(status.covering_agents)} of {minimum} required "
            f"agents in '{department_key}' hold active AgentCerts"
            + (f" for {caps}" if caps else "")
        )

    existing = (
        await session.execute(
            select(DeptCert).where(
                DeptCert.departmentId == dept.id,
                DeptCert.forgeContext == forge_context,
                DeptCert.status.in_(("active", "suspended")),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise CertIssuanceError(
            f"A {existing.status} DeptCert already exists for {department_key} / {forge_context}."
        )

    pack = (await session.execute(select(Pack).where(Pack.packId == pack_id))).scalar_one_or_none()
    if pack is None:
        raise CertIssuanceError(f"Pack not found: {pack_id}")

    runs = await _validate_dept_battery(session, dept_battery_run_ids)
    prereq_ids = await _covering_cert_ids(session, dept.id, caps)

    snapshot, now, expires = await _create_dept_snapshot(
        session, department_key, forge_context, tier, runs, approver_id, pack, prereq_ids
    )

    cert = DeptCert(
        departmentId=dept.id,
        forgeContext=forge_context,
        tier=tier,
        status="active",
        issuedAt=now,
        expiresAt=expires,
        certSnapshotId=snapshot.id,
        prerequisiteAgentCertIds=prereq_ids,
    )
    session.add(cert)
    await session.flush()
    session.add(
        CertLifecycleEvent(
            deptCertId=cert.id,
            event="issued",
            timestamp=now,
            actor=approver_id,
            reason=f"prerequisites met ({len(prereq_ids)} agent certs) + dept battery passed",
            snapshotIdAtEvent=snapshot.snapshotId,
        )
    )

    # Lineage: dept cert produced_by department, derived_from pack, evidenced_by snapshot,
    # and derived_from each prerequisite AgentCert (composition edges).
    from src.services.registry import add_edge, register_entry
    from src.services.registry.urn import cert_urn, evidence_urn, pack_urn

    c_urn = cert_urn(cert.id)
    await register_entry(
        session,
        c_urn,
        "cert",
        cert.id,
        {"forge_context": forge_context, "tier": tier, "kind": "dept"},
    )
    await register_entry(session, pack_urn(pack.packId), "pack", pack.packId, {})
    await add_edge(session, c_urn, pack_urn(pack.packId), "derived_from")
    await add_edge(session, c_urn, evidence_urn(snapshot.snapshotId), "evidenced_by")
    for aid in prereq_ids:
        await add_edge(session, c_urn, cert_urn(aid), "derived_from")

    await session.commit()
    await session.refresh(cert)
    await session.refresh(snapshot)
    return IssuedDeptCert(cert, snapshot, prereq_ids)


async def revoke_dept_cert(
    session: AsyncSession, dept_cert_id: str, reason: str, actor: str, *, status: str = "revoked"
) -> DeptCert:
    """Revoke (or suspend) a DeptCert. `status` = 'revoked' | 'suspended'."""
    cert = (
        await session.execute(select(DeptCert).where(DeptCert.id == dept_cert_id))
    ).scalar_one_or_none()
    if cert is None:
        raise CertIssuanceError(f"DeptCert not found: {dept_cert_id}")
    now = utcnow()
    cert.status = status
    if status == "revoked":
        cert.revokedAt = now
        cert.revocationReason = reason
    session.add(
        CertLifecycleEvent(
            deptCertId=cert.id,
            event="revoked" if status == "revoked" else "suspended",
            timestamp=now,
            actor=actor,
            reason=reason,
        )
    )
    await session.commit()
    await session.refresh(cert)
    return cert


async def recheck_dept_cert_coverage(
    session: AsyncSession, department_id: str, actor: str
) -> list[str]:
    """Auto-suspend any active DeptCert in the department whose AgentCert coverage dropped below the
    minimum (Revocation trigger #3: prerequisite dependency failure). Returns suspended cert ids."""
    dept_certs = (
        (
            await session.execute(
                select(DeptCert).where(
                    DeptCert.departmentId == department_id, DeptCert.status == "active"
                )
            )
        )
        .scalars()
        .all()
    )
    if not dept_certs:
        return []
    dept = (
        await session.execute(select(Department).where(Department.id == department_id))
    ).scalar_one_or_none()
    if dept is None:
        return []

    suspended: list[str] = []
    for cert in dept_certs:
        # Re-derive coverage against the caps originally required (inferred from the prerequisite
        # certs' caps), falling back to any-active if none were pinned.
        prereq_certs = (
            (
                await session.execute(
                    select(AgentCert).where(
                        AgentCert.id.in_(cert.prerequisiteAgentCertIds or ["none"])
                    )
                )
            )
            .scalars()
            .all()
        )
        caps = sorted({c.forgeCap for c in prereq_certs})
        status = await dept_prerequisite_status(session, dept.villageKey, caps)
        if not status.satisfied:
            await revoke_dept_cert(
                session,
                cert.id,
                f"prerequisite AgentCert coverage dropped below {status.required_min}",
                actor,
                status="suspended",
            )
            suspended.append(cert.id)
    return suspended

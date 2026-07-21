"""Certification registry — issue & revoke AgentCerts (blueprint §F.1, §F.2, §F.4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.agent import Agent
from src.models.ccb import CCB as CCBModel
from src.models.cert import AgentCert, CertLifecycleEvent, CertSnapshot
from src.models.pack import Pack
from src.models.run import Run
from src.models.scorecard import Scorecard
from src.services.cert.autonomy_ladder import LEVELS, demote, promote_on_first_cert
from src.services.cert.signer import encode_signature, get_signer
from src.services.cert.snapshot import CertSnapshotPayload, PinnedVersions
from src.services.evidence import store_evidence_bundle
from src.utils.time import utcnow


class CertIssuanceError(Exception):
    """Raised when a cert cannot be issued (bad battery, duplicate, missing entities)."""


@dataclass
class IssuedCert:
    agent_cert: AgentCert
    snapshot: CertSnapshot
    autonomy_from: str
    autonomy_to: str


async def _validate_battery(
    session: AsyncSession, agent: Agent, battery_run_ids: list[str]
) -> list[Run]:
    if len(battery_run_ids) < settings.cert_min_battery_size:
        raise CertIssuanceError(
            f"Battery too small: {len(battery_run_ids)} < {settings.cert_min_battery_size}"
        )
    runs: list[Run] = []
    for rid in battery_run_ids:
        run = (await session.execute(select(Run).where(Run.runId == rid))).scalar_one_or_none()
        if run is None:
            raise CertIssuanceError(f"Run not found: {rid}")
        if run.agentId != agent.id:
            raise CertIssuanceError(f"Run {rid} does not belong to agent {agent.villageAgentId}")
        card = (
            await session.execute(select(Scorecard).where(Scorecard.runId == run.id))
        ).scalar_one_or_none()
        if card is None or not card.readinessGatePassed:
            raise CertIssuanceError(f"Run {rid} did not pass the readiness gate")
        runs.append(run)
    return runs


async def issue_agent_cert(
    session: AsyncSession,
    agent_village_id: str,
    forge_cap: str,
    tier: str,
    battery_run_ids: list[str],
    approver_id: str,
    pack_id: str,
) -> IssuedCert:
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == agent_village_id))
    ).scalar_one_or_none()
    if agent is None:
        raise CertIssuanceError(f"Agent not found: {agent_village_id}")

    runs = await _validate_battery(session, agent, battery_run_ids)

    existing = (
        await session.execute(
            select(AgentCert).where(
                AgentCert.agentId == agent.id,
                AgentCert.forgeCap == forge_cap,
                AgentCert.status == "active",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise CertIssuanceError(
            f"Active cert already exists for {agent_village_id} / {forge_cap} (use renew)"
        )

    pack = (await session.execute(select(Pack).where(Pack.packId == pack_id))).scalar_one_or_none()
    if pack is None:
        raise CertIssuanceError(f"Pack not found: {pack_id}")

    # Village fingerprint pinned from a battery run's CCB.
    fingerprint = ""
    if runs[0].ccbPreId:
        ccb = (
            await session.execute(select(CCBModel).where(CCBModel.id == runs[0].ccbPreId))
        ).scalar_one_or_none()
        fingerprint = ccb.villageSchemaFingerprint if ccb else ""

    forge = forge_cap.split(".")[0]
    now = utcnow()
    expires = now + timedelta(days=settings.cert_validity_days)

    pinned = PinnedVersions(
        pack=pack.packId,
        scenario_library_hash=pack.yamlHash,
        forge_versions={forge: "sandbox.dev"},
        village_schema_fingerprint=fingerprint,
    )
    payload = CertSnapshotPayload(
        cert_type="agent_forge_cap",
        subject=agent_village_id,
        tier=tier,
        issued_at=now,
        expires_at=expires,
        pinned_versions=pinned.as_dict(),
        evidence_bundle_ref="",  # set below
        forge_cap=forge_cap,
    )

    content_hash = payload.content_hash()
    snapshot_id = f"certsnap:{content_hash[:16]}"

    bundle = {
        "snapshot_id": snapshot_id,
        "subject": agent_village_id,
        "forge_cap": forge_cap,
        "tier": tier,
        "approver_id": approver_id,
        "battery": [
            {"run_id": r.runId, "scenario_internal_id": r.scenarioId, "outcome": r.outcome}
            for r in runs
        ],
        "pinned_versions": pinned.as_dict(),
        "issued_at": now,
    }
    evidence_ref = store_evidence_bundle(snapshot_id.replace(":", "_"), bundle)
    payload.evidence_bundle_ref = evidence_ref

    # Re-hash + sign the finalized payload (now including the evidence ref).
    content_hash = payload.content_hash()
    snapshot_id = f"certsnap:{content_hash[:16]}"
    signer = get_signer()
    signature = encode_signature(signer.sign(payload.to_canonical().encode()))

    snapshot = CertSnapshot(
        snapshotId=snapshot_id,
        certType="agent_forge_cap",
        subject=agent_village_id,
        forgeCap=forge_cap,
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

    cert = AgentCert(
        agentId=agent.id,
        forgeCap=forge_cap,
        tier=tier,
        status="active",
        issuedAt=now,
        expiresAt=expires,
        certSnapshotId=snapshot.id,
    )
    session.add(cert)
    await session.flush()

    session.add(
        CertLifecycleEvent(
            agentCertId=cert.id,
            event="issued",
            timestamp=now,
            actor=approver_id,
            reason="battery passed",
            snapshotIdAtEvent=snapshot_id,
        )
    )

    from_level = agent.currentAutonomyLevel
    await promote_on_first_cert(session, agent)
    to_level = agent.currentAutonomyLevel

    await session.commit()
    await session.refresh(cert)
    await session.refresh(snapshot)
    return IssuedCert(cert, snapshot, from_level, to_level)


async def revoke_agent_cert(
    session: AsyncSession, cert_id: str, reason: str, actor: str
) -> AgentCert:
    cert = (
        await session.execute(select(AgentCert).where(AgentCert.id == cert_id))
    ).scalar_one_or_none()
    if cert is None:
        raise CertIssuanceError(f"Cert not found: {cert_id}")

    now = utcnow()
    cert.status = "revoked"
    cert.revokedAt = now
    cert.revocationReason = reason
    session.add(
        CertLifecycleEvent(
            agentCertId=cert.id, event="revoked", timestamp=now, actor=actor, reason=reason
        )
    )

    # Defensive demotion by one level on revocation.
    agent = (
        await session.execute(select(Agent).where(Agent.id == cert.agentId))
    ).scalar_one_or_none()
    if agent is not None:
        idx = (
            LEVELS.index(agent.currentAutonomyLevel) if agent.currentAutonomyLevel in LEVELS else 0
        )
        if idx > 0:
            await demote(session, agent, LEVELS[idx - 1], f"revocation: {reason}", actor)

    await session.commit()
    await session.refresh(cert)
    return cert

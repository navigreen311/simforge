"""Certification registry — issue & revoke AgentCerts (blueprint §F.1, §F.2, §F.4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.agent import Agent
from src.models.ccb import CCB as CCBModel
from src.models.cert import AgentCert, CertLifecycleEvent, CertSnapshot
from src.models.pack import Pack
from src.models.run import Run
from src.models.scorecard import Scorecard
from src.services.cert.autonomy_ladder import (
    LEVELS,
    demote,
    promote_on_first_cert,
    record_transition,
)
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


async def _create_snapshot(
    session: AsyncSession,
    agent_village_id: str,
    forge_cap: str,
    tier: str,
    runs: list[Run],
    approver_id: str,
    pack: Pack,
) -> tuple[CertSnapshot, datetime, datetime]:
    """Build + sign a CertSnapshot pinning the current version matrix. Shared by issue + reinstate,
    so both produce byte-identical canonical/signed payloads (ADR-0007)."""
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

    # Pin the real Forge version the battery ran against (drift canary compares against this).
    from src.services.forges.registry import get_forge_adapter

    try:
        forge_version = await get_forge_adapter(forge).get_current_version()
    except Exception:  # noqa: BLE001 — never fail issuance on a Forge lookup hiccup
        forge_version = f"{forge}.unknown"

    pinned = PinnedVersions(
        pack=pack.packId,
        scenario_library_hash=pack.yamlHash,
        forge_versions={forge: forge_version},
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

    snapshot_id = f"certsnap:{payload.content_hash()[:16]}"
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
    return snapshot, now, expires


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

    # A cert already occupies this (agent, forge_cap) pair (UNIQUE in the schema). An active one
    # blocks re-issue; a *suspended* one must be reinstated (re-certified), not re-issued.
    existing = (
        await session.execute(
            select(AgentCert).where(
                AgentCert.agentId == agent.id,
                AgentCert.forgeCap == forge_cap,
                AgentCert.status.in_(("active", "suspended")),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        verb = "Reinstate it" if existing.status == "suspended" else "Revoke it first"
        raise CertIssuanceError(
            f"A {existing.status} cert already exists for {agent_village_id} / {forge_cap}. "
            f"{verb} instead of re-issuing."
        )

    pack = (await session.execute(select(Pack).where(Pack.packId == pack_id))).scalar_one_or_none()
    if pack is None:
        raise CertIssuanceError(f"Pack not found: {pack_id}")

    snapshot, now, expires = await _create_snapshot(
        session, agent_village_id, forge_cap, tier, runs, approver_id, pack
    )

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
            snapshotIdAtEvent=snapshot.snapshotId,
        )
    )

    # Lineage + registry (blueprint §F.2 step 8).
    from src.services.registry import add_edge, register_entry
    from src.services.registry.urn import (
        agent_urn,
        cert_urn,
        constitution_urn,
        evidence_urn,
        pack_urn,
    )

    c_urn = cert_urn(cert.id)
    await register_entry(session, c_urn, "cert", cert.id, {"forge_cap": forge_cap, "tier": tier})
    await register_entry(
        session, agent_urn(agent.villageAgentId), "agent", agent.villageAgentId, {}
    )
    await register_entry(session, pack_urn(pack.packId), "pack", pack.packId, {})
    await add_edge(session, c_urn, agent_urn(agent.villageAgentId), "produced_by")
    await add_edge(session, c_urn, pack_urn(pack.packId), "derived_from")
    constitution_version = snapshot.pinnedVersions.get("constitution_version", "v1.0.0")
    await add_edge(session, c_urn, constitution_urn(constitution_version), "pinned_to")
    await add_edge(session, c_urn, evidence_urn(snapshot.snapshotId), "evidenced_by")

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
    # Real-time PEP cache invalidation (best-effort; §F.4).
    if agent is not None:
        from src.services.governance.revocation import publish_cert_event

        await publish_cert_event(agent.villageAgentId, cert.forgeCap, "revoked")
    return cert


async def reinstate_agent_cert(
    session: AsyncSession,
    cert_id: str,
    battery_run_ids: list[str],
    approver_id: str,
) -> IssuedCert:
    """Reinstate a **suspended** cert by re-certifying against the *current* version matrix.

    A cert suspended by the Drift Canary (Forge drift) or a constitution amendment is recovered by
    running a fresh passing battery: this pins a new snapshot against the now-current Forge (and
    constitution) versions, flips the cert back to active, and restores one autonomy level. The
    UNIQUE(agentId, forgeCap) constraint is respected — the existing cert row is updated in place
    (no re-issue), which is why suspended certs can't be re-`issue`d and must be reinstated."""
    cert = (
        await session.execute(select(AgentCert).where(AgentCert.id == cert_id))
    ).scalar_one_or_none()
    if cert is None:
        raise CertIssuanceError(f"Cert not found: {cert_id}")
    if cert.status != "suspended":
        raise CertIssuanceError(f"Only suspended certs can be reinstated (cert is '{cert.status}')")

    agent = (
        await session.execute(select(Agent).where(Agent.id == cert.agentId))
    ).scalar_one_or_none()
    if agent is None:
        raise CertIssuanceError("Cert's agent no longer exists")

    runs = await _validate_battery(session, agent, battery_run_ids)

    old_snap = (
        await session.execute(select(CertSnapshot).where(CertSnapshot.id == cert.certSnapshotId))
    ).scalar_one_or_none()
    pack_id = old_snap.pinnedVersions.get("pack") if old_snap else None
    pack = (
        (await session.execute(select(Pack).where(Pack.packId == pack_id))).scalar_one_or_none()
        if pack_id
        else None
    )
    if pack is None:
        raise CertIssuanceError("Original pack for this cert not found; cannot reinstate")

    snapshot, now, expires = await _create_snapshot(
        session, agent.villageAgentId, cert.forgeCap, cert.tier, runs, approver_id, pack
    )

    cert.status = "active"
    cert.certSnapshotId = snapshot.id
    cert.issuedAt = now
    cert.expiresAt = expires
    cert.revokedAt = None
    cert.revocationReason = None
    session.add(
        CertLifecycleEvent(
            agentCertId=cert.id,
            event="reinstated",
            timestamp=now,
            actor=approver_id,
            reason="re-certified against current versions",
            snapshotIdAtEvent=snapshot.snapshotId,
        )
    )

    # Restore one autonomy level (inverse of the defensive demote on suspension).
    from_level = agent.currentAutonomyLevel
    idx = LEVELS.index(from_level) if from_level in LEVELS else 0
    if idx < len(LEVELS) - 1:
        await record_transition(session, agent, LEVELS[idx + 1], "cert reinstated", approver_id)
    to_level = agent.currentAutonomyLevel

    await session.commit()
    await session.refresh(cert)
    await session.refresh(snapshot)
    # Reinstatement re-enables the cert → tell PEPs to drop any cached deny (best-effort; §F.4).
    from src.services.governance.revocation import publish_cert_event

    await publish_cert_event(agent.villageAgentId, cert.forgeCap, "reinstated")
    return IssuedCert(cert, snapshot, from_level, to_level)

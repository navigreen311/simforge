"""Drift Canary (blueprint §L.4 deferral; ADR-0017).

A cert pins the exact Forge version its battery ran against (`pinnedVersions.forge_versions`).
If that Forge later reports a different version, the certified behavior may no longer hold — the
cert's evidence is stale. The canary scans active certs, compares each pinned Forge version against
the Forge's *current* `get_current_version()`, and (by default) **auto-suspends** any cert whose
Forge has drifted, pending re-certification — mirroring the constitution-amendment auto-suspend.

A Forge that is unreachable (an HTTP sandbox that's down) is reported but **not** suspended — a
transient outage must not knock out certs. Sandbox-isolated + read-only against the Village.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert, CertLifecycleEvent, CertSnapshot
from src.services.cert.autonomy_ladder import LEVELS, demote
from src.services.forges.registry import get_forge_adapter
from src.utils.time import utcnow


@dataclass
class DriftFinding:
    cert_id: str
    agent_village_id: str
    forge: str
    forge_cap: str
    pinned_version: str
    current_version: str | None
    status: str  # "drift" | "unreachable"


async def _current_version(forge: str) -> tuple[str | None, bool]:
    """(version, reachable). Unreachable → (None, False), so we never suspend on an outage."""
    try:
        return await get_forge_adapter(forge).get_current_version(), True
    except Exception:  # noqa: BLE001 — any transport/lookup error = treat as unreachable
        return None, False


async def scan_forge_drift(
    session: AsyncSession, actor: str = "drift-canary", *, suspend: bool = True
) -> dict:
    """Scan active certs for Forge version drift. `suspend=False` is a dry run (report only)."""
    now = utcnow()
    certs = (
        (await session.execute(select(AgentCert).where(AgentCert.status == "active")))
        .scalars()
        .all()
    )
    findings: list[DriftFinding] = []
    suspended = 0
    # Cache current versions across certs so we hit each Forge once.
    version_cache: dict[str, tuple[str | None, bool]] = {}

    for cert in certs:
        snap = (
            await session.execute(
                select(CertSnapshot).where(CertSnapshot.id == cert.certSnapshotId)
            )
        ).scalar_one_or_none()
        if snap is None:
            continue
        pinned_forges: dict = snap.pinnedVersions.get("forge_versions", {}) or {}
        agent = (
            await session.execute(select(Agent).where(Agent.id == cert.agentId))
        ).scalar_one_or_none()
        agent_vid = agent.villageAgentId if agent else "?"

        cert_drifted = False
        for forge, pinned_version in pinned_forges.items():
            if forge not in version_cache:
                version_cache[forge] = await _current_version(forge)
            current, reachable = version_cache[forge]
            if not reachable:
                findings.append(
                    DriftFinding(
                        cert.id,
                        agent_vid,
                        forge,
                        cert.forgeCap,
                        pinned_version,
                        None,
                        "unreachable",
                    )
                )
                continue
            if current != pinned_version:
                cert_drifted = True
                findings.append(
                    DriftFinding(
                        cert.id, agent_vid, forge, cert.forgeCap, pinned_version, current, "drift"
                    )
                )

        if cert_drifted and suspend:
            cert.status = "suspended"
            reason = "forge drift (pinned Forge version no longer current)"
            session.add(
                CertLifecycleEvent(
                    agentCertId=cert.id,
                    event="suspended",
                    timestamp=now,
                    actor=actor,
                    reason=reason,
                    snapshotIdAtEvent=snap.snapshotId,
                )
            )
            # Defensive demotion by one level, as on revocation.
            if agent is not None:
                idx = (
                    LEVELS.index(agent.currentAutonomyLevel)
                    if agent.currentAutonomyLevel in LEVELS
                    else 0
                )
                if idx > 0:
                    await demote(session, agent, LEVELS[idx - 1], reason, actor)
            suspended += 1

    if suspend:
        await session.commit()

    drift_findings = [f for f in findings if f.status == "drift"]
    return {
        "scanned": len(certs),
        "drifted_certs": len({f.cert_id for f in drift_findings}),
        "suspended": suspended,
        "dry_run": not suspend,
        "findings": [asdict(f) for f in findings],
    }

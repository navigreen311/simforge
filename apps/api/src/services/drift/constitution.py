"""Constitution-version drift DETECTION (P0-B audit, Finding 2; display-only).

A cert pins the constitution version it was certified under. When the constitution is amended, certs
pinned to the prior version are *stale*. The Forge Drift Canary (ADR-0017) does not cover this — its
scan surface is Forge versions only. This module surfaces constitution staleness so the governance
console stops showing a false green on its most load-bearing invariant.

**Detection and display only.** It never suspends a cert: the enforcement policy (auto-suspend /
flag-and-grace / amendment-scoped) is a pending owner decision. Scans ALL certs (not just active) so
the console shows the real pinned-vs-current picture even when — as today — zero certs are active.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert, CertSnapshot
from src.models.governance import Constitution
from src.services.capabilities import describe_capability


def _pinned_constitution(pinned: dict | None) -> str | None:
    p = pinned or {}
    return p.get("constitution") or p.get("constitution_version") or p.get("constitutionVersion")


async def constitution_drift_report(session: AsyncSession) -> dict:
    """Per-cert pinned-constitution vs. current-active-constitution, with a stale flag."""
    current = (
        await session.execute(
            select(Constitution)
            .where(Constitution.supersededByVersion.is_(None))
            .order_by(Constitution.ratifiedAt.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    current_version = current.version if current else None

    certs = (await session.execute(select(AgentCert))).scalars().all()
    all_agents = (await session.execute(select(Agent))).scalars().all()
    agents = {a.id: a.villageAgentId for a in all_agents}
    agent_names = {a.villageAgentId: a.name for a in all_agents}
    snaps = {s.id: s for s in (await session.execute(select(CertSnapshot))).scalars().all()}

    findings: list[dict] = []
    for cert in certs:
        snap = snaps.get(cert.certSnapshotId)
        pinned = _pinned_constitution(snap.pinnedVersions if snap else None)
        stale = current_version is not None and pinned is not None and pinned != current_version
        findings.append(
            {
                "cert_id": cert.id,
                "agent": agents.get(cert.agentId, cert.agentId),
                "capability": cert.forgeCap,  # raw cap id; label via cap_labels (shared catalog)
                "cert_status": cert.status,
                "pinned_constitution": pinned,
                "current_constitution": current_version,
                "stale": stale,
            }
        )

    # Reuse the shared capability catalog + agent display-name map (as Incident/Readiness do) so
    # the 10 otherwise-identical rows are distinguishable and rows can link to cert/agent.
    cap_labels = {cap: describe_capability(cap) for cap in {f["capability"] for f in findings}}
    stale_total = sum(1 for f in findings if f["stale"])
    active_stale = sum(1 for f in findings if f["stale"] and f["cert_status"] == "active")
    return {
        "current_constitution": current_version,
        "scanned": len(findings),
        "stale_certs": stale_total,
        "active_stale_certs": active_stale,
        "enforced": False,  # detection only; suspension policy pending (Finding 2)
        "cap_labels": cap_labels,
        "agent_names": agent_names,
        "findings": findings,
    }

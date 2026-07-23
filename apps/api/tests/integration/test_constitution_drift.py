"""Constitution-drift DETECTION (P0-B audit, Finding 2). Detection only — never suspends."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert, CertSnapshot
from src.models.governance import Constitution
from src.utils.time import utcnow


async def _seed_stale_cert(session: AsyncSession) -> str:
    now = utcnow()
    session.add_all(
        [
            Constitution(
                version="v1.0.0",
                ratifiedAt=now - timedelta(days=2),
                ratifiedBy="ivan",
                yamlContent="preamble: v1",
                contentHash="h0",
                supersededByVersion="v1.0.1",
                supersededAt=now,
            ),
            Constitution(
                version="v1.0.1",
                ratifiedAt=now,
                ratifiedBy="ivan",
                yamlContent="preamble: v1.1",
                contentHash="h1",
                supersededByVersion=None,
            ),
        ]
    )
    snap = CertSnapshot(
        snapshotId="certsnap:stale1",
        certType="agent_forge_cap",
        subject="david_kim",
        forgeCap="cre-forge.x",
        tier="foundational",
        issuedAt=now,
        expiresAt=now + timedelta(days=90),
        pinnedVersions={"constitution": "v1.0.0", "forge_versions": {}},
        evidenceBundleRef="ev1",
        signingKeyId="k1",
        signature="s1",
        contentHash="c1",
    )
    session.add(snap)
    await session.flush()
    agent = (
        await session.execute(select(Agent).where(Agent.villageAgentId == "david_kim"))
    ).scalar_one()
    cert = AgentCert(
        agentId=agent.id,
        forgeCap="cre-forge.x",
        tier="foundational",
        status="active",  # active + pinned to superseded => stale but must NOT be auto-suspended
        issuedAt=now,
        expiresAt=now + timedelta(days=90),
        certSnapshotId=snap.id,
    )
    session.add(cert)
    await session.commit()
    return cert.id


async def test_constitution_drift_detects_but_never_enforces(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    cert_id = await _seed_stale_cert(db_session)

    resp = await client.get("/api/drift/constitution")
    assert resp.status_code == 200
    body = resp.json()

    assert body["current_constitution"] == "v1.0.1"
    assert body["enforced"] is False  # DETECTION ONLY — the guardrail
    assert body["scanned"] == 1
    assert body["stale_certs"] == 1
    assert body["active_stale_certs"] == 1
    f = body["findings"][0]
    assert f["pinned_constitution"] == "v1.0.0"
    assert f["current_constitution"] == "v1.0.1"
    assert f["stale"] is True

    # The cert must be UNCHANGED — detection never mutates cert status.
    cert = (await db_session.execute(select(AgentCert).where(AgentCert.id == cert_id))).scalar_one()
    assert cert.status == "active"


async def test_constitution_versions_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_stale_cert(db_session)
    body = (await client.get("/api/constitution/versions")).json()
    versions = {v["version"]: v["active"] for v in body["versions"]}
    assert versions == {"v1.0.0": False, "v1.0.1": True}

    # Full text is retrievable per version (the viewer needs it).
    v11 = (await client.get("/api/constitution/v1.0.1")).json()
    assert v11["yaml"] == "preamble: v1.1"
